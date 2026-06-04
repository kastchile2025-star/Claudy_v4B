import { Search, Settings, Volume2, Send } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useStore } from '../store/useStore'
import openCodeService from '../services/opencode'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import { Message } from '../types'

export default function ChatArea() {
  const {
    currentSession,
    messages,
    selectedModel,
    addMessage,
    setLoading,
    isLoading,
    config,
  } = useStore()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [isStreaming, setIsStreaming] = useState(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || !currentSession) return

    // Agregar mensaje del usuario
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      model: selectedModel?.id,
    }

    addMessage(userMessage)
    setLoading(true)
    setIsStreaming(true)

    try {
      // Crear mensaje asistente vacío
      const assistantMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        model: selectedModel?.id,
      }

      addMessage(assistantMessage)

      // Obtener respuesta de OpenCode con streaming
      let fullResponse = ''

      await openCodeService.sendMessageStream(
        content,
        (chunk) => {
          fullResponse += chunk

          // Actualizar mensaje asistente
          addMessage({
            ...assistantMessage,
            content: fullResponse,
          })
        },
        {
          model: selectedModel?.id,
          temperature: config.temperature,
          maxTokens: config.maxTokens,
          systemPrompt: config.systemPrompt,
        }
      )
    } catch (error) {
      console.error('Error sending message:', error)

      const errorMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Algo salió mal'}`,
        timestamp: new Date(),
      }

      addMessage(errorMessage)
    } finally {
      setLoading(false)
      setIsStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border-dark bg-gradient-to-r from-bg-dark/50 to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center animate-pulse">
            <span className="text-white font-bold">✨</span>
          </div>
          <div>
            <h2 className="text-lg font-semibold">Asistente IA</h2>
            <p className="text-xs text-text-muted">
              Modelo Neural v4.0 • Precisión Avanzada
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button className="p-2 hover:bg-slate-800 rounded-lg transition-all text-text-muted hover:text-white">
            <Search size={20} />
          </button>
          <button className="p-2 hover:bg-slate-800 rounded-lg transition-all text-text-muted hover:text-white">
            <Settings size={20} />
          </button>
          <button className="p-2 hover:bg-slate-800 rounded-lg transition-all text-text-muted hover:text-white">
            <Volume2 size={20} />
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-24 h-24 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center mb-4 animate-pulse">
              <span className="text-5xl">🤖</span>
            </div>
            <h3 className="text-2xl font-bold mb-2">¡Hola Felipe! 👋</h3>
            <p className="text-text-muted max-w-md">
              Soy Claudy, tu asistente IA. ¿En qué puedo ayudarte hoy?
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {isStreaming && (
          <div className="flex items-center gap-2 text-text-muted">
            <span>Claudy está escribiendo</span>
            <span className="flex gap-1">
              <span className="w-2 h-2 bg-primary rounded-full animate-pulse"></span>
              <span
                className="w-2 h-2 bg-primary rounded-full animate-pulse"
                style={{ animationDelay: '0.2s' }}
              ></span>
              <span
                className="w-2 h-2 bg-primary rounded-full animate-pulse"
                style={{ animationDelay: '0.4s' }}
              ></span>
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <ChatInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  )
}
