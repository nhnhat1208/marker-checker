export function formatChatTimestamp(timestamp: number) {
  return new Intl.DateTimeFormat([], {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(timestamp))
}
