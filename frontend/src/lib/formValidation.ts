/**
 * 表单校验工具。
 *
 * 1. 前端即时校验（onBlur / 提交前）
 * 2. 后端 422 错误解析（Pydantic errors → 字段级错误映射）
 */

// ── 前端校验规则 ──

export type ValidationRule = {
  required?: boolean;
  min?: number;        // 数值最小值
  minLength?: number;  // 字符串最小长度
  pattern?: RegExp;
  message: string;
};

export type FieldRules = Record<string, ValidationRule[]>;

/**
 * 按规则校验单个字段，返回第一个错误消息或 undefined。
 */
export function validateField(value: unknown, rules: ValidationRule[]): string | undefined {
  for (const rule of rules) {
    const strVal = String(value ?? "").trim();

    if (rule.required && !strVal) {
      return rule.message;
    }
    if (rule.minLength !== undefined && strVal.length < rule.minLength) {
      return rule.message;
    }
    if (rule.min !== undefined && Number(value) < rule.min) {
      return rule.message;
    }
    if (rule.pattern && !rule.pattern.test(strVal)) {
      return rule.message;
    }
  }
  return undefined;
}

/**
 * 批量校验所有字段，返回 { 字段名: 错误消息 }。
 */
export function validateAll(
  data: Record<string, unknown>,
  rules: FieldRules,
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const [field, fieldRules] of Object.entries(rules)) {
    const err = validateField(data[field], fieldRules);
    if (err) errors[field] = err;
  }
  return errors;
}

// ── 后端 422 错误解析 ──

interface PydanticError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * 字段错误中文映射（常见的 Pydantic 错误翻译）。
 */
const MSG_MAP: Record<string, string> = {
  "Input should be greater than 0": "必须大于 0",
  "String should have at least 1 character": "不能为空",
  "Field required": "必填项",
  "value is not a valid integer": "请填写整数",
  "value is not a valid float": "请填写数字",
};

/**
 * 字段名中文映射。
 */
const FIELD_LABEL: Record<string, string> = {
  name: "商品名称",
  price_min: "最低价",
  price_max: "最高价",
  moq: "最小起订量",
  unit: "计量单位",
  category_code: "品类",
  brand: "品牌",
  origin: "产地",
  hs_code: "HS 编码",
  lead_time_days: "交期",
};

/**
 * 解析后端 422 Pydantic 错误数组，转为 { 字段名: 中文错误消息 }。
 */
export function parsePydanticErrors(errors: PydanticError[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const err of errors) {
    // loc 通常是 ["body", "field_name"]，取最后一个
    const field = String(err.loc[err.loc.length - 1]);
    const label = FIELD_LABEL[field] || field;
    const msg = MSG_MAP[err.msg] || err.msg;
    result[field] = `${label}：${msg}`;
  }
  return result;
}

/**
 * 从 ApiError 中提取字段级错误。
 * 兼容 422 Pydantic 错误和业务错误。
 */
export function extractFieldErrors(error: any): Record<string, string> {
  // 422 Pydantic errors
  if (error?.data?.errors && Array.isArray(error.data.errors)) {
    return parsePydanticErrors(error.data.errors);
  }
  return {};
}

/**
 * 生成用于 alert 的汇总错误文本（fallback 用，优先用字段级展示）。
 */
export function errorSummary(errors: Record<string, string>): string {
  const items = Object.values(errors);
  if (items.length === 0) return "请检查表单内容";
  return items.join("\n");
}
