import MarkerLogo from '@/components/brand/MarkerLogo'

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5">
      <MarkerLogo className="mt-0.5 h-7 w-7" title="Marker Checker agent" />
      <div className="rounded-2xl rounded-tl-sm border border-border bg-background px-4 py-3 shadow-sm">
        <span className="flex h-3.5 items-center gap-1" aria-label="Typing">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/70" />
        </span>
      </div>
    </div>
  )
}
