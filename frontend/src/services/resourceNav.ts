/**
 * 资源页路由传参通道。
 *
 * App 是 stage 状态机（无 URL 路由参数），页面经 AnimatePresence 按 key 重挂载：
 * 导航前由来源页写入参数，资源页挂载时读取——等价于路由 query，不触碰路由结构。
 *
 * - kpId：粘性。资源页及其子组件（外部资源 / 错题强化）在整个停留期间持续读取；
 *   未经学习路径页进入（如侧边栏直达）时保持上次值，初始为 CURRENT_KP_ID（nn），
 *   与修复前行为一致。
 * - entryTab：一次性（读后即清）。避免侧边栏再次进入资源页时残留落点。
 */
import { CURRENT_KP_ID, kpById } from '../data/knowledgePoints'

let kpId: string = CURRENT_KP_ID
let entryTab: string | null = null

/** 导航去资源页前调用：指定目标知识点与（可选）落点 Tab。未知 kpId 回退默认。 */
export function setResourceNav(nextKpId: string, nextEntryTab?: string): void {
  kpId = kpById(nextKpId) ? nextKpId : CURRENT_KP_ID
  entryTab = nextEntryTab ?? null
}

/** 资源页当前知识点 id（粘性）。 */
export function getResourceKpId(): string {
  return kpId
}

/** 资源页落点 Tab（一次性：读取后即清空）。 */
export function consumeResourceEntryTab(): string | null {
  const t = entryTab
  entryTab = null
  return t
}
