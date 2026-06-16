import { type CSSProperties } from 'react'
import { cn } from '@/lib/utils'

type Props = {
  className?: string
  title?: string
  style?: CSSProperties
}

export default function MarkerLogo({ className, title = 'Marker Checker', style }: Props) {
  return (
    <img
      src="/favicon.svg"
      alt={title}
      role="img"
      className={cn('shrink-0', className)}
      style={style}
    />
  )
}
