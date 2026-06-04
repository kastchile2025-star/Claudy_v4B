import { useEffect } from 'react'
import { useStore } from './store/useStore'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import SettingsPanel from './components/SettingsPanel'

function App() {
  const { theme, initializeStore } = useStore()

  useEffect(() => {
    initializeStore()
  }, [])

  return (
    <div className={`${theme === 'dark' ? 'dark' : ''}`}>
      <div className="flex h-screen bg-bg-darker text-white">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          <ChatArea />
        </div>

        {/* Settings Panel (toggle) */}
        <SettingsPanel />
      </div>
    </div>
  )
}

export default App
