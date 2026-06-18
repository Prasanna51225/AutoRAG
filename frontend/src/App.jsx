// frontend/src/App.jsx
import { useState, useEffect, useCallback } from 'react'
import { sendQuery, uploadFile, getIngestionStatus } from './services/api'
import { useLocalStorage } from './hooks/useLocalStorage'
import { useDarkMode } from './hooks/useDarkMode'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import InputBox from './components/InputBox'

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function deriveTitle(query) {
  // Use first 40 chars of first user message as the session title
  return query.length > 40 ? query.slice(0, 40).trimEnd() + '…' : query
}

export default function App() {
  const [sessions, setSessions] = useLocalStorage('autorag_sessions_v2', [])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [darkMode, setDarkMode] = useDarkMode()

  // Sync messages from selected session
  useEffect(() => {
    if (currentSessionId) {
      const session = sessions.find(s => s.id === currentSessionId)
      setMessages(session ? (session.messages || []) : [])
    } else {
      setMessages([])
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId])

  const persistMessages = useCallback((sessionId, newMessages, titleOverride) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId
        ? {
            ...s,
            messages: newMessages,
            updatedAt: Date.now(),
            ...(titleOverride ? { title: titleOverride } : {}),
          }
        : s
    ))
  }, [setSessions])

  const createNewChat = useCallback(() => {
    const newId = generateId()
    setSessions(prev => [
      {
        id: newId,
        title: 'New conversation',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      },
      ...prev,
    ])
    setCurrentSessionId(newId)
    setMessages([])
    return newId
  }, [setSessions])

  const selectSession = (id) => setCurrentSessionId(id)

  const deleteSession = useCallback((id) => {
    setSessions(prev => prev.filter(s => s.id !== id))
    if (id === currentSessionId) {
      setCurrentSessionId(null)
      setMessages([])
    }
  }, [setSessions, currentSessionId])

  const renameSession = useCallback((id, newTitle) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title: newTitle } : s))
  }, [setSessions])

  const clearHistory = () => {
    setSessions([])
    setCurrentSessionId(null)
    setMessages([])
  }

  const handleSendMessage = async (query) => {
    let sessionId = currentSessionId
    let isNewSession = false

    if (!sessionId) {
      sessionId = generateId()
      isNewSession = true
      setSessions(prev => [
        {
          id: sessionId,
          title: deriveTitle(query),  // title set immediately from first message
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
        ...prev,
      ])
      setCurrentSessionId(sessionId)
    }

    const userMsg = { role: 'user', content: query, timestamp: Date.now() }
    const messagesWithUser = [...messages, userMsg]
    setMessages(messagesWithUser)

    // Update session: set title from first real message if brand new
    setSessions(prev => prev.map(s =>
      s.id === sessionId
        ? {
            ...s,
            messages: messagesWithUser,
            updatedAt: Date.now(),
            ...(isNewSession ? { title: deriveTitle(query) } : {}),
          }
        : s
    ))

    setIsLoading(true)

    try {
      const response = await sendQuery(query)
      const assistantMsg = {
        role: 'assistant',
        content: response.answer,
        metadata: response.metadata,
        timestamp: Date.now(),
      }
      const finalMessages = [...messagesWithUser, assistantMsg]
      setMessages(finalMessages)
      persistMessages(sessionId, finalMessages)
    } catch (error) {
      console.error('Query error:', error)
      const errorMsg = {
        role: 'assistant',
        content: 'Sorry, an error occurred while processing your request. Please try again.',
        timestamp: Date.now(),
      }
      const finalMessages = [...messagesWithUser, errorMsg]
      setMessages(finalMessages)
      persistMessages(sessionId, finalMessages)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAttachFile = async (file) => {
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = generateId()
      const title = `File: ${file.name}`
      setSessions(prev => [
        { id: sessionId, title, messages: [], createdAt: Date.now(), updatedAt: Date.now() },
        ...prev,
      ])
      setCurrentSessionId(sessionId)
    }

    const uploadingMsg = {
      role: 'system',
      content: `Uploading ${file.name}…`,
      isUploading: true,
      timestamp: Date.now(),
    }
    const msgsWithUpload = [...messages, uploadingMsg]
    setMessages(msgsWithUpload)
    persistMessages(sessionId, msgsWithUpload)
    setIsUploading(true)

    const updateLastMsg = (newContent, extra = {}) => {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: newContent, ...extra }
        persistMessages(sessionId, updated)
        return updated
      })
    }

    try {
      const uploadRes = await uploadFile(file, (percent) => {
        updateLastMsg(`Uploading ${file.name}… ${percent}%`)
      })
      const taskId = uploadRes.task_id

      let completed = false
      let attempts = 0
      while (!completed && attempts < 180) {
        await new Promise(r => setTimeout(r, 2000))
        const statusRes = await getIngestionStatus(taskId)
        if (statusRes.status === 'completed') {
          completed = true
          const chunks = statusRes.result?.chunks_processed || 0
          updateLastMsg(
            `✅ "${file.name}" ingested (${chunks} chunks). You can now ask questions about it.`,
            { isUploading: false }
          )
        } else if (statusRes.status === 'failed') {
          throw new Error(statusRes.error || 'Ingestion failed')
        }
        attempts++
      }
      if (!completed) {
        updateLastMsg(
          `⚠️ "${file.name}" ingestion is taking longer than expected. Content may not be ready yet.`,
          { isUploading: false }
        )
      }
    } catch (error) {
      console.error('Upload error:', error)
      updateLastMsg(`❌ Failed to upload "${file.name}": ${error.message}`, { isUploading: false })
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className={`flex h-screen overflow-hidden ${darkMode ? 'dark' : ''}`}>
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={createNewChat}
        onSelectSession={selectSession}
        onDeleteSession={deleteSession}
        onRenameSession={renameSession}
        onClearHistory={clearHistory}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
      />
      <div className="flex-1 flex flex-col bg-white dark:bg-[#212121] min-w-0">
        <ChatArea messages={messages} isLoading={isLoading} />
        <InputBox
          onSendMessage={handleSendMessage}
          onAttachFile={handleAttachFile}
          isLoading={isLoading}
          isUploading={isUploading}
        />
      </div>
    </div>
  )
}
