// frontend/src/components/ChatArea.jsx
import { useEffect, useRef } from 'react'
import Message from './Message'
import { BrainCircuit } from 'lucide-react'

export default function ChatArea({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center flex-col gap-4 text-center px-6">
        <div className="w-12 h-12 rounded-full bg-[#2f2f2f] flex items-center justify-center">
          <BrainCircuit size={24} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-[#ececec] mb-1">AutoRAG</h2>
          <p className="text-[#8e8ea0] text-sm max-w-xs">
            Upload a document and ask questions. The reflexion loop improves retrieval quality automatically.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-2">
        {messages.map((msg, i) => (
          <Message key={i} {...msg} />
        ))}

        {isLoading && (
          <div className="flex gap-3 py-4">
            <div className="w-7 h-7 rounded-full bg-[#2f2f2f] flex items-center justify-center shrink-0 mt-0.5">
              <BrainCircuit size={14} className="text-white" />
            </div>
            <div className="flex items-center gap-1 pt-1.5">
              <span className="w-2 h-2 bg-[#8e8ea0] rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-[#8e8ea0] rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-[#8e8ea0] rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
