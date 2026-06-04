import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { Message } from '../types'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isUser = message.role === 'user'

  return (
    <div
      className={`flex items-start gap-3 animate-slideIn ${
        isUser ? 'justify-end' : 'justify-start'
      }`}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center flex-shrink-0">
          <span className="text-sm font-bold">C</span>
        </div>
      )}

      {/* Message Bubble */}
      <div
        className={`max-w-2xl px-4 py-3 rounded-lg ${
          isUser
            ? 'bg-primary text-white rounded-br-none'
            : 'card-dark rounded-bl-none'
        }`}
      >
        <div className="prose prose-invert max-w-none text-sm">
          <ReactMarkdown
            components={{
              code: ({ node, inline, className, children, ...props }: any) => {
                const match = /language-(\w+)/.exec(className || '')
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={atomDark}
                    language={match[1]}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className="bg-slate-800 px-2 py-1 rounded text-primary-light" {...props}>
                    {children}
                  </code>
                )
              },
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({ children }) => (
                <ul className="list-disc list-inside mb-2 ml-4">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside mb-2 ml-4">{children}</ol>
              ),
              a: ({ children, href }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  {children}
                </a>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0 border border-border-dark">
          <span className="text-sm font-bold">F</span>
        </div>
      )}

      {/* Actions */}
      {!isUser && message.content && (
        <div className="flex flex-col gap-1 ml-2">
          <button
            onClick={handleCopy}
            className="p-1 hover:bg-slate-800 rounded transition-all text-text-muted hover:text-white"
            title="Copiar"
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
      )}
    </div>
  )
}
