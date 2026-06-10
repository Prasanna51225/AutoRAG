import { Plus, Trash2, MessageSquare } from 'lucide-react'
import ThemeToggle from './ThemeToggle'

export default function Sidebar({ sessions, currentSessionId, onNewChat, onSelectSession, onClearHistory, darkMode, setDarkMode }) {
  return (
    <aside className="w-64 bg-slate-100 dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col h-full">
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
        <h1 className="font-semibold text-slate-800 dark:text-slate-100">AutoRAG</h1>
        <ThemeToggle darkMode={darkMode} setDarkMode={setDarkMode} />
      </div>
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-card px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors duration-150"
        >
          <Plus size={16} /> New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`w-full text-left px-3 py-2 rounded-card text-sm flex items-center gap-2 transition-colors duration-150 ${
              session.id === currentSessionId
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800'
            }`}
          >
            <MessageSquare size={14} />
            <span className="truncate">{session.title || 'New conversation'}</span>
          </button>
        ))}
      </div>
      <div className="p-3 border-t border-slate-200 dark:border-slate-800">
        <button
          onClick={onClearHistory}
          className="w-full flex items-center justify-center gap-2 text-red-600 dark:text-red-400 text-sm hover:bg-red-50 dark:hover:bg-red-950/30 rounded-card px-3 py-2 transition-colors duration-150"
        >
          <Trash2 size={14} /> Clear history
        </button>
      </div>
    </aside>
  )
}