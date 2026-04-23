import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Small wrapper around react-markdown tuned for chat bubbles.
 *
 * - GFM enabled (tables, task lists, strikethrough, autolinks).
 * - `prose` gives reasonable defaults; prose-* modifiers tighten the
 *   vertical rhythm so bubbles don't balloon on short messages.
 * - Links open in a new tab with rel=noopener so we don't leak the
 *   session cookie via referer-like mechanisms.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <div
      className="prose prose-sm max-w-none
        prose-p:my-1
        prose-headings:my-2 prose-headings:font-semibold
        prose-ul:my-1 prose-ol:my-1 prose-li:my-0
        prose-pre:my-2 prose-pre:bg-gray-900 prose-pre:text-gray-100
        prose-code:text-[0.9em] prose-code:bg-gray-200 prose-code:rounded prose-code:px-1 prose-code:py-0.5 prose-code:before:content-none prose-code:after:content-none
        prose-a:text-indigo-700 prose-a:underline prose-a:break-all
        prose-blockquote:my-2 prose-blockquote:border-l-4 prose-blockquote:pl-3 prose-blockquote:text-gray-600
        prose-hr:my-3
        prose-table:my-2
      "
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
