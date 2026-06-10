import { useState, useEffect, useCallback, useRef } from 'react'
import { sendQuery, uploadFile, getIngestionStatus } from './services/api'
import { useLocalStorage } from './hooks/useLocalStorage'
import { useDarkMode } from './hooks/useDarkMode'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import InputBox from './components/InputBox'

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export default function App() {
  const [sessions, setSessions] = useLocalStorage('chat_sessions', [])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [darkMode, setDarkMode] = useDarkMode()
  const pendingMessageRef = useRef(null)

  // Load current session messages
  useEffect(() => {
    if (currentSessionId) {
      const session = sessions.find(s => s.id === currentSessionId)
      if (session) {
        setMessages(session.messages || [])
      } else {
        setMessages([])
      }
    } else {
      setMessages([])
    }
  }, [currentSessionId, sessions])

  const saveMessages = useCallback((sessionId, newMessages) => {
    setSessions(prev => prev.map(s => 
      s.id === sessionId ? { ...s, messages: newMessages, updatedAt: Date.now() } : s
    ))
  }, [setSessions])

  const createNewChat = () => {
    const newId = generateId()
    const newSession = {
      id: newId,
      title: 'New conversation',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    setSessions(prev => [newSession, ...prev])
    setCurrentSessionId(newId)
    return newId
  }

  const selectSession = (id) => {
    setCurrentSessionId(id)
  }

  const clearHistory = () => {
    setSessions([])
    setCurrentSessionId(null)
    setMessages([])
  }

  const addMessage = (role, content, metadata = null, isUploadingFlag = false) => {
    const newMessages = [...messages, { role, content, metadata, isUploading: isUploadingFlag, timestamp: Date.now() }]
    setMessages(newMessages)
    if (currentSessionId) {
      saveMessages(currentSessionId, newMessages)
    }
    return newMessages
  }

  const updateLastMessage = (content, metadata = null) => {
    const newMessages = [...messages]
    if (newMessages.length > 0) {
      newMessages[newMessages.length - 1].content = content
      if (metadata) newMessages[newMessages.length - 1].metadata = metadata
      setMessages(newMessages)
      if (currentSessionId) {
        saveMessages(currentSessionId, newMessages)
      }
    }
  }

  const handleSendMessage = async (query) => {
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createNewChat()
      // Small delay to ensure state updates before adding message
      await new Promise(r => setTimeout(r, 50))
    }

    // Add user message immediately
    const userMsg = { role: 'user', content: query, timestamp: Date.now() }
    setMessages(prev => [...prev, userMsg])
    if (sessionId) {
      setSessions(prev => prev.map(s => 
        s.id === sessionId ? { ...s, messages: [...(s.messages || []), userMsg], updatedAt: Date.now() } : s
      ))
    }
    setIsLoading(true)

    try {
      const response = await sendQuery(query)
      const assistantMsg = { role: 'assistant', content: response.answer, metadata: response.metadata, timestamp: Date.now() }
      setMessages(prev => [...prev, assistantMsg])
      if (sessionId) {
        setSessions(prev => prev.map(s => 
          s.id === sessionId ? { ...s, messages: [...(s.messages || []), assistantMsg], updatedAt: Date.now() } : s
        ))
      }
    } catch (error) {
      console.error('Query error:', error)
      const errorMsg = { role: 'assistant', content: 'Sorry, an error occurred while processing your request. Please try again.', timestamp: Date.now() }
      setMessages(prev => [...prev, errorMsg])
      if (sessionId) {
        setSessions(prev => prev.map(s => 
          s.id === sessionId ? { ...s, messages: [...(s.messages || []), errorMsg], updatedAt: Date.now() } : s
        ))
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleAttachFile = async (file) => {
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createNewChat()
      await new Promise(r => setTimeout(r, 50))
    }

    const systemMsg = { role: 'system', content: `Uploading ${file.name}...`, isUploading: true, timestamp: Date.now() }
    setMessages(prev => [...prev, systemMsg])
    if (sessionId) {
      setSessions(prev => prev.map(s => 
        s.id === sessionId ? { ...s, messages: [...(s.messages || []), systemMsg], updatedAt: Date.now() } : s
      ))
    }
    setIsUploading(true)

    try {
      const uploadRes = await uploadFile(file, (percent) => {
        const updatedMsg = { ...systemMsg, content: `Uploading ${file.name}... ${percent}%` }
        setMessages(prev => prev.map((m, i) => i === prev.length-1 ? updatedMsg : m))
        if (sessionId) {
          setSessions(prevS => prevS.map(s => 
            s.id === sessionId ? { ...s, messages: s.messages?.map((m, i) => i === s.messages.length-1 ? updatedMsg : m) || [] } : s
          ))
        }
      })
      const taskId = uploadRes.task_id

      let completed = false
      let attempts = 0
      while (!completed && attempts < 60) {
        await new Promise(r => setTimeout(r, 2000))
        const statusRes = await getIngestionStatus(taskId)
        if (statusRes.status === 'completed') {
          completed = true
          const chunks = statusRes.result?.chunks_processed || 0
          const successMsg = { role: 'system', content: `✅ File "${file.name}" ingested successfully (${chunks} chunks). You can now ask questions about it.`, timestamp: Date.now() }
          setMessages(prev => [...prev.slice(0, -1), successMsg])
          if (sessionId) {
            setSessions(prevS => prevS.map(s => 
              s.id === sessionId ? { ...s, messages: [...(s.messages?.slice(0, -1) || []), successMsg], updatedAt: Date.now() } : s
            ))
          }
        } else if (statusRes.status === 'failed') {
          throw new Error(statusRes.error || 'Ingestion failed')
        }
        attempts++
      }
      if (!completed) {
        const timeoutMsg = { role: 'system', content: `⚠️ File "${file.name}" ingestion is taking longer than expected. You can still ask questions, but new content may not be available yet.`, timestamp: Date.now() }
        setMessages(prev => [...prev.slice(0, -1), timeoutMsg])
        if (sessionId) {
          setSessions(prevS => prevS.map(s => 
            s.id === sessionId ? { ...s, messages: [...(s.messages?.slice(0, -1) || []), timeoutMsg], updatedAt: Date.now() } : s
          ))
        }
      }
    } catch (error) {
      console.error('Upload error:', error)
      const errorMsg = { role: 'system', content: `❌ Failed to upload "${file.name}": ${error.message}`, timestamp: Date.now() }
      setMessages(prev => [...prev.slice(0, -1), errorMsg])
      if (sessionId) {
        setSessions(prevS => prevS.map(s => 
          s.id === sessionId ? { ...s, messages: [...(s.messages?.slice(0, -1) || []), errorMsg], updatedAt: Date.now() } : s
        ))
      }
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={createNewChat}
        onSelectSession={selectSession}
        onClearHistory={clearHistory}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
      />
      <div className="flex-1 flex flex-col">
        <ChatArea messages={messages} isLoading={isLoading} isUploading={isUploading} />
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