import { X, Sun, Moon } from 'lucide-react'
import { useStore } from '../store/useStore'

export default function SettingsPanel() {
  const {
    showSettings,
    toggleSettings,
    config,
    updateConfig,
    theme,
    toggleTheme,
    models,
    selectedModel,
    setSelectedModel,
  } = useStore()

  if (!showSettings) return null

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={toggleSettings}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-screen w-96 bg-bg-dark border-l border-border-dark flex flex-col z-50 animate-slideIn shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border-dark">
          <h2 className="text-xl font-bold">Configuración</h2>
          <button
            onClick={toggleSettings}
            className="p-2 hover:bg-slate-800 rounded-lg transition-all"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Modelo */}
          <div>
            <label className="block text-sm font-semibold mb-3">Modelo</label>
            <select
              value={selectedModel?.id || ''}
              onChange={(e) => {
                const model = models.find((m) => m.id === e.target.value)
                if (model) setSelectedModel(model)
              }}
              className="w-full px-3 py-2 bg-slate-900 border border-border-dark rounded-lg focus:border-primary focus:ring-1 focus:ring-primary"
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
            {selectedModel && (
              <p className="text-xs text-text-muted mt-2">
                {selectedModel.description}
              </p>
            )}
          </div>

          {/* Temperatura */}
          <div>
            <label className="block text-sm font-semibold mb-3">
              Temperatura: {config.temperature.toFixed(2)}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={config.temperature}
              onChange={(e) =>
                updateConfig({ temperature: parseFloat(e.target.value) })
              }
              className="w-full"
            />
            <p className="text-xs text-text-muted mt-2">
              Controla la creatividad de las respuestas (0=determinista, 1=creativo)
            </p>
          </div>

          {/* Max Tokens */}
          <div>
            <label className="block text-sm font-semibold mb-3">
              Máx. Tokens: {config.maxTokens}
            </label>
            <input
              type="range"
              min="256"
              max="8192"
              step="256"
              value={config.maxTokens}
              onChange={(e) =>
                updateConfig({ maxTokens: parseInt(e.target.value) })
              }
              className="w-full"
            />
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-semibold mb-3">
              Instrucción del Sistema
            </label>
            <textarea
              value={config.systemPrompt}
              onChange={(e) =>
                updateConfig({ systemPrompt: e.target.value })
              }
              className="w-full h-24 px-3 py-2 bg-slate-900 border border-border-dark rounded-lg focus:border-primary focus:ring-1 focus:ring-primary resize-none text-sm"
            />
          </div>

          {/* Tools */}
          <div>
            <label className="block text-sm font-semibold mb-3">
              Herramientas
            </label>
            <div className="space-y-2">
              {Object.entries(config.tools).map(([tool, enabled]) => (
                <label key={tool} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) =>
                      updateConfig({
                        tools: {
                          ...config.tools,
                          [tool]: e.target.checked,
                        },
                      })
                    }
                    className="w-4 h-4 rounded border-border-dark"
                  />
                  <span className="text-sm capitalize">
                    {tool === 'exec' && '⚙️ Ejecutar'}
                    {tool === 'read' && '📖 Leer'}
                    {tool === 'write' && '✏️ Escribir'}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Tema */}
          <div>
            <label className="block text-sm font-semibold mb-3">Tema</label>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  if (theme === 'light') toggleTheme()
                }}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg transition-all ${
                  theme === 'dark'
                    ? 'bg-primary text-white'
                    : 'bg-slate-800 text-text-muted hover:bg-slate-700'
                }`}
              >
                <Moon size={18} />
                Oscuro
              </button>
              <button
                onClick={() => {
                  if (theme === 'dark') toggleTheme()
                }}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg transition-all ${
                  theme === 'light'
                    ? 'bg-primary text-white'
                    : 'bg-slate-800 text-text-muted hover:bg-slate-700'
                }`}
              >
                <Sun size={18} />
                Claro
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border-dark">
          <button
            onClick={toggleSettings}
            className="w-full py-2 bg-primary hover:bg-primary-dark text-white font-semibold rounded-lg transition-all"
          >
            Aplicar cambios
          </button>
        </div>
      </div>
    </>
  )
}
