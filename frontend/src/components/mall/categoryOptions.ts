import type { CategoryTreeNode } from "@/lib/api/categories";

/** 品类行要展示的节点:未选/找不到→一级;有子类→子类;叶子→父级的子类(叶子是一级时回一级列表)。 */
export function categoryOptions(tree: CategoryTreeNode[], code: string): CategoryTreeNode[] {
  if (!code) return tree;
  const walk = (nodes: CategoryTreeNode[]): CategoryTreeNode[] | null => {
    for (const n of nodes) {
      if (n.code === code) return n.children?.length ? n.children : nodes;
      const hit = n.children?.length ? walk(n.children) : null;
      if (hit) return hit;
    }
    return null;
  };
  return walk(tree) ?? tree;
}
