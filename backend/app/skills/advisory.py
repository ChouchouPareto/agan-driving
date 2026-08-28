import re


def _with_evidence(message: str, evidence: list[dict] | None) -> str:
    if not evidence:
        return message
    sources = []
    for item in evidence:
        effective = f"，生效/适用时间：{item['effective_at']}" if item.get("effective_at") else ""
        sources.append(f"{item['source_org']}《{item['title']}》{effective}\n{item['source_url']}")
    return f"{message}\n\n来源：\n" + "\n".join(sources)


def advisory_response(intent: str, text: str, evidence: list[dict] | None = None) -> str:
    """Return a safe first-turn answer for non-question-bank driving knowledge.

    These responses deliberately separate stable learning guidance from policy facts
    that require a region and an effective date before retrieval can be trusted.
    """
    if intent == "EMOTIONAL_SUPPORT":
        if re.search(r"考不过|挂科|没信心", text):
            return "听起来你最担心的是考试结果。先别把一次考试等同于学不会：我们可以先找出最没把握的科目，再定一个今天就能完成的小目标。你现在更担心理论题、场地操作，还是上路时紧张？"
        if re.search(r"教练|挨骂|被骂|害怕练车", text):
            return "被催促或被批评后紧张很正常，不代表你不适合学车。先把具体动作和情绪分开：告诉我当时练的项目、卡在哪一步，我帮你整理成下一次上车前可以照着做的三步；如果沟通持续让你不舒服，也可以提交给校长协调。"
        if re.search(r"麻烦|心累|不想学|不想继续|学不动", text):
            return "学车流程多、排期又不完全由自己控制，觉得麻烦很正常。我们先不逼自己把全部都扛住：你现在最烦的是记题、练车、约考，还是和教练沟通？告诉我一个，我先陪你把这一块变简单。"
        return "我听见你现在有些紧张。我们先不要求一次解决全部问题：慢慢呼吸一下，然后只选最困扰的一件事。是怕考试、怕上路、记不住题，还是和教练沟通有压力？我陪你把它拆小。"
    if intent == "LICENSE_TIMELINE":
        if evidence:
            facts = evidence[0]["summary"]
            return _with_evidence(f"先给你一个能落地的底线：{facts} 但这是最早预约条件，不是保证拿证日期；还要看培训完成度、当地考位和是否一次通过。告诉我城市、C1还是C2、当前到哪一步，我再帮你估算更贴近实际的区间。", evidence)
        return "拿证周期不能只用一个固定天数回答。它通常由报名与体检、学时与训练完成度、当地预约排队、各科通过情况共同决定。要估算最快周期，请告诉我所在城市、准驾车型、是否已报名，以及目前到哪个科目；涉及当地最短间隔或新规时，我会按地区和生效日期核对后再回答，不做包过或固定天数承诺。"
    if intent == "POLICY_REGULATION":
        if evidence:
            return _with_evidence(evidence[0]["summary"] + " 如果你问的是本地学时或预约口径，请再告诉我省市，我会继续按当地现行文件核对。", evidence)
        return "政策和考试规则有地区与生效时间差异。请补充所在省市、准驾车型，以及你看到的规定名称或发布日期；我会优先检索现行有效来源。没有命中可靠来源时，我会明确说暂时无法确认，并建议向当地交管部门或驾校校长核实。"
    if intent == "LEARNING_PROCESS":
        message = "常见学车流程是：报名建档与体检 → 科目一理论学习和考试 → 科目二场地训练与考试 → 科目三道路训练与考试 → 安全文明驾驶常识考试（通常称科目四）→ 领证。实际训练与预约进度以当地规则和学员档案为准。你告诉我当前阶段，我可以给你生成下一步清单。"
        return _with_evidence(message, evidence)
    if intent == "INDUSTRY_KNOWLEDGE":
        message = "驾培服务通常包含报名建档、理论学习、训练排期、考试预约和异常协调。选驾校或班型时，重点确认收费包含项、训练方式与频次、教练与车辆安排、补训补考规则和退转学约定；涉及你所在驾校的合同或收费，请只描述条款，不要上传身份证或缴费单，我可以帮你整理核对问题。"
        return _with_evidence(message, evidence)
    return "你可以告诉我所在地区、准驾车型和当前学习阶段，我会把行业信息、学习流程与可执行建议分开说明；涉及政策和时效的数据会先核对来源。"
