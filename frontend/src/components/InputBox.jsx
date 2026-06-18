// frontend/src/components/InputBox.jsx
import { useState, useRef, useEffect } from 'react'
import { ArrowUp, Paperclip } from 'lucide-react'

export default function InputBox({ onSendMessage, onAttachFile, isLoading, isUploading }) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
    }
  }, [message])

  const canSend = message.trim() && !isLoading && !isUploading

  const handleSubmit = () => {
    if (canSend) {
      onSendMessage(message.trim())
      setMessage('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      onAttachFile(file)
      e.target.value = ''
    }
  }

  return (
    <div className="px-4 pb-4 pt-2 bg-[#212121]">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-[#2f2f2f] rounded-2xl px-4 py-3">
          {/* Attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isUploading}
            className="p-1.5 text-[#8e8ea0] hover:text-[#ececec] disabled:opacity-40 transition-colors shrink-0 mb-0.5"
            title="Attach file (.txt or .pdf)"
          >
            <Paperclip size={18} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={e => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isUploading ? 'Ingesting file…' :
              isLoading ? 'Thinking…' :
              'Ask a question about your document…'
            }
            disabled={isLoading || isUploading}
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-[#ececec] placeholder-[#8e8ea0] text-sm leading-relaxed max-h-[200px] disabled:opacity-50"
          />

          {/* Send button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSend}
            className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors mb-0.5 ${
              canSend
                ? 'bg-white hover:bg-gray-200 text-black'
                : 'bg-[#3d3d3d] text-[#8e8ea0] cursor-not-allowed'
            }`}
            title="Send"
          >
            <ArrowUp size={16} />
          </button>
        </div>

        <p className="text-center text-[#8e8ea0] text-xs mt-2">
          AutoRAG answers only from your uploaded documents.
        </p>
      </div>
    </div>
  )
}
