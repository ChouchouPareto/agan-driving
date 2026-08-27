export type LearningStage = { id: string; label: string; shortLabel: string };
export type LicenseCategory = { code: string; name: string; group: string; stages: LearningStage[] };

const FOUR_STAGES: LearningStage[] = [
  { id: "subject-1", label: "科目一 · 理论", shortLabel: "科目一" },
  { id: "subject-2", label: "科目二 · 场地", shortLabel: "科目二" },
  { id: "subject-3", label: "科目三 · 路考", shortLabel: "科目三" },
  { id: "subject-4", label: "科目四 · 安全文明", shortLabel: "科目四" },
];
const THREE_STAGES: LearningStage[] = [
  { id: "subject-1", label: "科目一 · 理论", shortLabel: "科目一" },
  { id: "subject-2", label: "科目二 · 场地", shortLabel: "科目二" },
  { id: "subject-3", label: "科目三 · 路考与安全文明", shortLabel: "科目三" },
];
const C6_STAGES: LearningStage[] = [
  { id: "subject-2", label: "科目二 · 场地", shortLabel: "科目二" },
  { id: "subject-3", label: "科目三 · 路考", shortLabel: "科目三" },
  { id: "subject-4", label: "安全文明驾驶常识", shortLabel: "安全文明" },
];

export const LICENSE_CATEGORIES: LicenseCategory[] = [
  { code: "A1", name: "大型客车", group: "客运", stages: FOUR_STAGES },
  { code: "A2", name: "重型牵引挂车", group: "货运", stages: FOUR_STAGES },
  { code: "A3", name: "城市公交车", group: "客运", stages: FOUR_STAGES },
  { code: "B1", name: "中型客车", group: "客运", stages: FOUR_STAGES },
  { code: "B2", name: "大型货车", group: "货运", stages: FOUR_STAGES },
  { code: "C1", name: "小型汽车", group: "小型汽车", stages: FOUR_STAGES },
  { code: "C2", name: "小型自动挡汽车", group: "小型汽车", stages: FOUR_STAGES },
  { code: "C3", name: "低速载货汽车", group: "小型汽车", stages: FOUR_STAGES },
  { code: "C4", name: "三轮汽车", group: "小型汽车", stages: FOUR_STAGES },
  { code: "C5", name: "残疾人专用自动挡汽车", group: "小型汽车", stages: FOUR_STAGES },
  { code: "C6", name: "轻型牵引挂车", group: "小型汽车", stages: C6_STAGES },
  { code: "D", name: "普通三轮摩托车", group: "摩托车", stages: THREE_STAGES },
  { code: "E", name: "普通二轮摩托车", group: "摩托车", stages: THREE_STAGES },
  { code: "F", name: "轻便摩托车", group: "摩托车", stages: THREE_STAGES },
  { code: "M", name: "轮式专用机械车", group: "专项", stages: THREE_STAGES },
  { code: "N", name: "无轨电车", group: "专项", stages: THREE_STAGES },
  { code: "P", name: "有轨电车", group: "专项", stages: THREE_STAGES },
];

export const licenseCategory = (code: string) => LICENSE_CATEGORIES.find(item => item.code === code) ?? LICENSE_CATEGORIES.find(item => item.code === "C1")!;
export const learningStage = (license: string, stage: string) => licenseCategory(license).stages.find(item => item.id === stage) ?? licenseCategory(license).stages[0];
export const hasCurrentContent = (license: string, stage: string) => ["C1", "C2"].includes(license) && ["subject-1", "subject-4"].includes(stage);
