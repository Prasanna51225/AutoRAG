import { useState, useRef, useEffect } from 'react'
import { Send, Paperclip } from 'lucide-react'

export default function InputBox({ onSendMessage, onAttachFile, isLoading, isUploading }) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [message])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (message.trim() && !isLoading && !isUploading) {
      onSendMessage(message.trim())
      setMessage('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleAttachClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      onAttachFile(file)
      e.target.value = '' // allow re-upload same file
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <button
          type="button"
          onClick={handleAttachClick}
          disabled={isLoading || isUploading}
          className="p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 disabled:opacity-50 transition-colors duration-150"
          aria-label="Attach file"
        >
          <Paperclip size={20} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isUploading ? 'Uploading file...' : 'Ask a question or upload a file...'}
          disabled={isLoading || isUploading}
          rows={1}
          className="flex-1 resize-none rounded-card border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-2 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-accent-light dark:focus:ring-accent-dark transition-colors duration-150"
        />
        <button
          type="submit"
          disabled={!message.trim() || isLoading || isUploading}
          className="p-2 bg-slate-900 dark:bg-slate-700 text-white rounded-card disabled:opacity-50 hover:bg-slate-800 dark:hover:bg-slate-600 transition-colors duration-150"
          aria-label="Send"
        >
          <Send size={20} />
        </button>
      </div>
    </form>
  )
}