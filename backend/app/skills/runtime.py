"""Read-only skill tools. Side effects require a separate user-confirmed API."""
from collections import Counter
from dataclasses import dataclass, field
import re

from sqlalchemy import select

from app.knowledge.advisory_service import retrieve_advisory_documents
from app.knowledge.mnemonics import mnemonic_for
from app.models import KnowledgeVersion, StandardQuestion, StudentQuestionProgress

ADVISORY_INTENTS = {"INDUSTRY_KNOWLEDGE", "LEARNING_PROCESS", "POLICY_REGULATION", "LICENSE_TIMELINE"}
POLICY_INTENTS = {"LICENSE_TIMELINE", "POLICY_REGULATION", "LEARNING_PROCESS"}
CAPABILITIES = ["文字讲题与拍题识别", "顺序刷题、模拟考试、错题本、收藏", "常见场景卡和口诀", "查看自己的练习记录", "交流练车压力", "确认后提交给校长并查看回复"]


@dataclass
class SkillContext:
    data: dict = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    facts: str = ""
    tools_used: list[str] = field(default_factory=list)
    handoff_available: bool = False


def execute_skill(db, student, intent: str, text: str, context: dict, question=None) -> SkillContext:
    result = SkillContext()
    if intent in ADVISORY_INTENTS:
        query = text + (" 最快拿证周期" if intent == "LICENSE_TIMELINE" else "")
        result.evidence = retrieve_advisory_documents(db, query, intent, context["license_type"], context["region"])
        result.tools_used.append("advisory_knowledge")
        if intent in POLICY_INTENTS:
            result.facts = "\n\n".join(
                f"{item['summary']}\n依据：{item['title']}（资料生效时间：{item.get('effective_at') or '未标注'}）。{item['source_url']}"
                for item in result.evidence
            )
            if intent == "LICENSE_TIMELINE" and result.evidence:
                result.facts += "\n这是资料中的最早预约条件，不是保证拿证日期；具体还要核对当地考位、培训完成情况和考试结果。"
            if result.evidence and re.search(r"最近|最新|新规|现在", text):
                result.facts = "目前查到的是下面这些历史资料，不能据此确认最近是否有调整；最新要求请向当地交管或培训主管部门核实。\n\n" + result.facts
            result.data["policy_boundary"] = "现有资料摘要会由程序单独展示；不能据此确认最新本地政策。没有实时考位与排期，不能估算拿证日期。"
    if intent == "MNEMONIC_HELP":
        current_phrase = mnemonic_for(text)
        stem = text if current_phrase else question.raw_text if question else text
        explanation = question.answer.detail if question and question.answer else ""
        phrase = current_phrase or mnemonic_for(stem, explanation)
        result.tools_used.append("reviewed_mnemonics")
        result.data["reviewed_mnemonic"] = phrase or None
        result.data["question"] = stem
        if phrase:
            result.facts = f"记这句就好：{phrase}\n这是帮助回想规则的口诀，做题还要看清适用条件。"
            result.evidence = [{"title": "已编排口诀", "summary": phrase, "source_type": "reviewed_mnemonic"}]
    if intent == "LEARNING_PROGRESS":
        rows = db.execute(select(StudentQuestionProgress, StandardQuestion).join(StandardQuestion, StandardQuestion.id == StudentQuestionProgress.standard_question_id).join(KnowledgeVersion, KnowledgeVersion.id == StudentQuestionProgress.knowledge_version_id).where(StudentQuestionProgress.student_id == student.id, KnowledgeVersion.school_id == student.school_id, KnowledgeVersion.status == "ACTIVE")).all()
        attempts = sum(p.attempts for p, _ in rows)
        correct = sum(p.correct_attempts for p, _ in rows)
        weak = Counter()
        for progress, q in rows:
            if progress.wrong_attempts:
                for point in q.knowledge_points or ["未分类题目"]:
                    weak[str(point)] += progress.wrong_attempts
        result.tools_used.append("progress_tracker")
        result.data["progress"] = {"attempted_questions": sum(p.attempts > 0 for p, _ in rows), "attempts": attempts, "correct": correct, "weak_points": weak.most_common(3)}
        if attempts:
            result.facts = f"你目前有 {attempts} 次答题记录，答对 {correct} 次，正确率 {correct / attempts:.0%}。"
            if weak:
                result.facts += "\n目前错得较多的知识点：" + "、".join(f"{point}（{count}次）" for point, count in weak.most_common(3)) + "。这些是已有记录，不是完整能力诊断。"
        else:
            result.facts = "查过了，目前还没有你的练习记录，暂时算不出正确率和薄弱点。"
    if intent in {"HUMAN_HELP", "SCHOOL_SERVICE"}:
        result.tools_used.append("principal_ticket")
        result.handoff_available = True
        result.data["school_service"] = {"timetable_available": False, "fees_available": False, "handoff": "下方有‘确认提交给校长’按钮。点击后才提交本次会话中的学员问题，并打开工单页面；现在尚未提交。"}
    if intent == "PRODUCT_HELP":
        result.tools_used.append("capability_catalog")
        result.data["available_capabilities"] = CAPABILITIES
    if intent == "PRACTICAL_TRAINING":
        result.tools_used.append("training_playbook")
        result.data["training_playbook"] = {"approach": "先问清具体项目、压哪边线、发生在进库前还是进库后；已经说明的不要重复问。", "boundary": "点位因车辆、座椅和场地不同，不提供通用固定角度、距离或打轮圈数；下一次在教练现场监督下核对。"}
    return result


def invalid_skill_reply(reply: str, intent: str, runtime: SkillContext) -> bool:
    if re.search(r"三长一短|三短一长|选最[长短]|看选项长度|靠(?:语感|常识|猜)|蒙[对题]|必过|包过", reply):
        return True
    # Legal facts are rendered from retrieved text, never regenerated by the LLM.
    prose = re.sub(r"\b[ABC][1-6]\b", "", reply, flags=re.I)
    if intent in POLICY_INTENTS and re.search(r"(?:界面|系统|页面).{0,25}(?:会|同步|展示|提示|通知)|(?:会|将).{0,10}(?:展示|同步).{0,15}(?:时间|考位|排期)", prose):
        return True
    if intent in POLICY_INTENTS and re.search(r"\d|[零一二两三四五六七八九十百]+(?:个)?(?:天|日|周|月|年|小时)|满.{0,8}(?:约考|预约)|规定|新规|法定|大纲|(?:界面|系统|我会).{0,12}(?:同步|提示|通知).{0,12}(?:考|时间)|界面会同步", prose):
        return True
    if intent == "MNEMONIC_HELP":
        return bool(re.search(r"口诀|记住|这样记|让直行|让左转|选[对错]|正确答案", reply))
    if intent == "LEARNING_PROGRESS" and re.search(r"\d|看不到|没法查|不能查|无法查看", reply):
        return True
    if runtime.handoff_available and re.search(r"已(?:经)?(?:帮你)?(?:提交|联系|转接)|没有权限|无法.{0,4}(?:转接|联系)|找.?客服入口", reply):
        return True
    return False
