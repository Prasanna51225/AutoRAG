import { useEffect, useRef } from 'react'
import Message from './Message'

export default function ChatArea({ messages, isLoading, isUploading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center flex-col text-center p-8">
        <div className="max-w-md">
          <h2 className="text-2xl font-semibold text-slate-700 dark:text-slate-300 mb-2">Welcome to AutoRAG</h2>
          <p className="text-slate-500 dark:text-slate-400">
            Ask a question or upload a document (.txt or .pdf) to start a conversation.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((msg, idx) => (
        <Message
          key={idx}
          role={msg.role}
          content={msg.content}
          metadata={msg.metadata}
          isUploading={msg.isUploading}
        />
      ))}
      {isLoading && (
        <div className="message-assistant">
          <div className="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}