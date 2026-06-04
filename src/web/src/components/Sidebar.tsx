import { Plus, Trash2, Settings, LogOut, Menu, X } from 'lucide-react'
import { useState } from 'react'
import { useStore } from '../store/useStore'

export default function Sidebar() {
  const {
    sessions,
    currentSessionId,
    createSession,
    selectSession,
    deleteSession,
    toggleSettings,
  } = useStore()

  const [isOpen, setIsOpen] = useState(true)

  return (
    <>
      {/* Toggle button for mobile */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden"
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      <aside
        className={`${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } fixed lg:relative w-64 h-screen bg-slate-900/80 backdrop-blur border-r border-border-dark flex flex-col transition-transform duration-300 z-40 lg:z-0 lg:translate-x-0`}
      >
        {/* Header */}
        <div className="p-6 border-b border-border-dark">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">C</span>
            </div>
            <h1 className="text-xl font-bold gradient-text">CLAUDY AI</h1>
          </div>
          <p className="text-sm text-text-muted">Tu asistente inteligente</p>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <span className="pulse-dot"></span>
            <span className="text-text-muted">En línea</span>
            <span className="text-primary ml-2">• Memoria activa</span>
          </div>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-primary to-secondary hover:opacity-90 text-white font-semibold py-3 rounded-lg transition-all"
          >
            <Plus size={20} />
            Nueva conversación
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-3 space-y-2">
          <h3 className="text-xs font-semibold text-text-muted uppercase px-2 py-2">
            CONVERSACIONES
          </h3>

          {sessions.length === 0 ? (
            <p className="text-xs text-text-muted text-center py-4">
              Sin conversaciones
            </p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className={`group relative p-3 rounded-lg cursor-pointer transition-all ${
                  currentSessionId === session.id
                    ? 'bg-primary/20 border border-primary'
                    : 'hover:bg-slate-800/50 border border-transparent'
                }`}
                onClick={() => selectSession(session.id)}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {session.title}
                    </p>
                    <p className="text-xs text-text-muted truncate">
                      {session.messages.length} mensajes
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteSession(session.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition-all"
                  >
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border-dark space-y-2">
          <button
            onClick={toggleSettings}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-800 rounded-lg transition-all"
          >
            <Settings size={18} />
            Configuración
          </button>
          <div className="p-3 bg-slate-800/50 rounded-lg">
            <p className="text-xs font-medium text-white mb-2">Felipe Dev</p>
            <p className="text-xs text-text-muted mb-3">PRO • felipe@dev.com</p>
            <button className="w-full flex items-center justify-center gap-2 text-xs text-red-400 hover:bg-red-500/10 py-2 rounded transition-all">
              <LogOut size={14} />
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>

      {/* Overlay on mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 lg:hidden z-30"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  )
}
