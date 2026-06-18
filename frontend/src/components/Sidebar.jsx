// frontend/src/components/Sidebar.jsx
import { useState, useRef, useEffect } from 'react'
import { Plus, Trash2, MessageSquare, Pencil, Check, X, Sun, Moon } from 'lucide-react'

function SidebarItem({ session, isActive, onSelect, onDelete, onRename }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(session.title)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const commitRename = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== session.title) onRename(session.id, trimmed)
    setEditing(false)
  }

  const cancelRename = () => {
    setDraft(session.title)
    setEditing(false)
  }

  return (
    <div
      className={`group relative flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
        isActive
          ? 'bg-[#2f2f2f] text-white'
          : 'text-[#ececec] hover:bg-[#2f2f2f]'
      }`}
      onClick={() => !editing && onSelect(session.id)}
    >
      <MessageSquare size={15} className="shrink-0 text-[#8e8ea0]" />

      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') commitRename()
            if (e.key === 'Escape') cancelRename()
          }}
          onClick={e => e.stopPropagation()}
          className="flex-1 bg-transparent border-b border-[#8e8ea0] outline-none text-white text-sm"
        />
      ) : (
        <span className="flex-1 truncate">{session.title}</span>
      )}

      {editing ? (
        <div className="flex gap-1" onClick={e => e.stopPropagation()}>
          <button onClick={commitRename} className="text-green-400 hover:text-green-300">
            <Check size={13} />
          </button>
          <button onClick={cancelRename} className="text-red-400 hover:text-red-300">
            <X size={13} />
          </button>
        </div>
      ) : (
        <div className="hidden group-hover:flex gap-1 shrink-0" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => { setDraft(session.title); setEditing(true) }}
            className="text-[#8e8ea0] hover:text-white p-0.5 rounded"
            title="Rename"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(session.id)}
            className="text-[#8e8ea0] hover:text-red-400 p-0.5 rounded"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
    </div>
  )
}

export default function Sidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onRenameSession,
  onClearHistory,
  darkMode,
  setDarkMode,
}) {
  return (
    <aside className="w-[260px] shrink-0 bg-[#171717] flex flex-col h-full">
      {/* Header */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 text-[#ececec] hover:bg-[#2f2f2f] px-3 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          New chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5">
        {sessions.length === 0 && (
          <p className="text-[#8e8ea0] text-xs px-2 py-4 text-center">No conversations yet</p>
        )}
        {sessions.map(session => (
          <SidebarItem
            key={session.id}
            session={session}
            isActive={session.id === currentSessionId}
            onSelect={onSelectSession}
            onDelete={onDeleteSession}
            onRename={onRenameSession}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="px-3 pb-4 pt-2 border-t border-[#2f2f2f] flex items-center justify-between">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-2 rounded-lg text-[#8e8ea0] hover:text-white hover:bg-[#2f2f2f] transition-colors"
          title="Toggle theme"
        >
          {darkMode ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {sessions.length > 0 && (
          <button
            onClick={onClearHistory}
            className="flex items-center gap-1.5 text-[#8e8ea0] hover:text-red-400 text-xs px-2 py-1.5 rounded-lg hover:bg-[#2f2f2f] transition-colors"
            title="Clear all conversations"
          >
            <Trash2 size={13} /> Clear all
          </button>
        )}
      </div>
    </aside>
  )
}
