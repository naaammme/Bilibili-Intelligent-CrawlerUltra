/**
 * 格式化时间
 * @param {string} timeStr - ISO时间字符串
 * @returns {string} 格式化后的时间
 */
export function formatTime(timeStr) {
  try {
    const date = new Date(timeStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return timeStr
  }
}

/**
 * HTML转义
 * @param {string} text - 需要转义的文本
 * @returns {string} 转义后的文本
 */
export function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}