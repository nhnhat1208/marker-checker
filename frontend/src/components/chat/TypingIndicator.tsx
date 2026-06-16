export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary shadow-sm">
        <span className="select-none text-xs font-bold text-primary-foreground">M</span>
      </div>
      <div className="rounded-2xl rounded-tl-sm border border-border bg-background px-4 py-3 shadow-sm">
        <p className="mb-1.5 text-xs text-muted-foreground">Parsing and routing…</p>
        <span className="flex h-3.5 items-center gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
        </span>
      </div>
    </div>
  )
}
