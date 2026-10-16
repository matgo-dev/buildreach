import { describe, expect, it } from "vitest";
import type { CategoryTreeNode } from "@/lib/api/categories";
import { categoryOptions } from "./categoryOptions";

const node = (code: string, children: CategoryTreeNode[] = []) =>
  ({ code, name: code, children }) as unknown as CategoryTreeNode;

const tree = [
  node("01", [node("01.001", [node("01.001.001"), node("01.001.002")]), node("01.002")]),
  node("33", [node("33.001"), node("33.005")]),
  node("99"),
];
const codes = (ns: CategoryTreeNode[]) => ns.map((n) => n.code);

describe("categoryOptions", () => {
  it("未选品类 → 一级", () => {
    expect(codes(categoryOptions(tree, ""))).toEqual(["01", "33", "99"]);
  });

  it("选了有子类的节点 → 其子类(一级与中间级都适用)", () => {
    expect(codes(categoryOptions(tree, "33"))).toEqual(["33.001", "33.005"]);
    expect(codes(categoryOptions(tree, "01.001"))).toEqual(["01.001.001", "01.001.002"]);
  });

  it("选到叶子 → 同级兄弟", () => {
    expect(codes(categoryOptions(tree, "01.001.002"))).toEqual(["01.001.001", "01.001.002"]);
    expect(codes(categoryOptions(tree, "33.005"))).toEqual(["33.001", "33.005"]);
  });

  it("没有子类的一级 → 一级列表;不在树里的 code → 一级兜底", () => {
    expect(codes(categoryOptions(tree, "99"))).toEqual(["01", "33", "99"]);
    expect(codes(categoryOptions(tree, "77.001"))).toEqual(["01", "33", "99"]);
  });
});
