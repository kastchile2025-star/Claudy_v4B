import { Send, Paperclip, Smile } from 'lucide-react'
import { useState } from 'react'

interface ChatInputProps {
  onSendMessage: (message: string) => void
  isLoading: boolean
}

export default function ChatInput({
  onSendMessage,
  isLoading,
}: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    onSendMessage(input)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as any)
    }
  }

  return (
    <div className="px-6 py-4 border-t border-border-dark bg-gradient-to-t from-bg-dark/50">
      <form onSubmit={handleSubmit} className="flex gap-3">
        {/* Input Area */}
        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe un mensaje..."
            disabled={isLoading}
            className="w-full h-12 px-4 py-2 bg-slate-900/50 border border-primary/30 hover:border-primary/50 focus:border-primary rounded-full resize-none placeholder-text-muted"
            rows={1}
          />

          {/* Action Buttons */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-2">
            <button
              type="button"
              className="p-1.5 hover:bg-slate-800 rounded-full transition-all text-text-muted hover:text-white"
            >
              <Paperclip size={18} />
            </button>
            <button
              type="button"
              className="p-1.5 hover:bg-slate-800 rounded-full transition-all text-text-muted hover:text-white"
            >
              <Smile size={18} />
            </button>
          </div>
        </div>

        {/* Send Button */}
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="px-6 py-2 bg-gradient-to-r from-primary to-secondary hover:opacity-90 disabled:opacity-50 text-white font-semibold rounded-full transition-all flex items-center justify-center min-w-fit"
        >
          {isLoading ? (
            <span className="animate-spin">⏳</span>
          ) : (
            <Send size={20} />
          )}
        </button>
      </form>

      {/* Help Text */}
      <div className="flex justify-center gap-4 text-xs text-text-muted mt-2">
        <span>Presiona <kbd className="bg-slate-800 px-2 py-1 rounded">Enter</kbd> para enviar</span>
        <span>•</span>
        <span><kbd className="bg-slate-800 px-2 py-1 rounded">Shift + Enter</kbd> para nueva línea</span>
        <span>•</span>
        <span><kbd className="bg-slate-800 px-2 py-1 rounded">Esc</kbd> para cerrar</span>
      </div>
    </div>
  )
}
