import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ChevronDown, ChevronUp, FileText } from 'lucide-react'

export default function Message({ role, content, metadata, isUploading = false }) {
  const [showDetails, setShowDetails] = useState(false)

  if (role === 'system') {
    return (
      <div className="flex justify-center my-2">
        <div className="bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-xs px-3 py-1 rounded-full flex items-center gap-1">
          {isUploading && <div className="animate-spin h-3 w-3 border-2 border-slate-400 border-t-transparent rounded-full"></div>}
          <span>{content}</span>
        </div>
      </div>
    )
  }

  if (role === 'user') {
    return (
      <div className="message-user">
        <div className="prose prose-sm dark:prose-invert max-w-none">{content}</div>
      </div>
    )
  }

  return (
    <div className="message-assistant">
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
      
      {metadata && (
        <div className="mt-3 pt-2 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300 transition-colors duration-150"
          >
            {showDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {showDetails ? 'Hide details' : 'Show details'}
          </button>
          
          {showDetails && (
            <div className="mt-2 text-xs text-slate-600 dark:text-slate-400 space-y-1 bg-slate-50 dark:bg-slate-900/50 p-2 rounded-card">
              <div><span className="font-medium">Loop count:</span> {metadata.loop_count}</div>
              <div><span className="font-medium">Critic score:</span> {metadata.critic_score?.toFixed(2) || 'N/A'}</div>
              <div><span className="font-medium">Critic reason:</span> {metadata.critic_reason || 'N/A'}</div>
              <div><span className="font-medium">Total latency:</span> {metadata.total_latency_ms} ms</div>
              <div><span className="font-medium">Chunks used:</span> {metadata.chunks_used}</div>
              {metadata.final_query !== metadata.original_query && (
                <div><span className="font-medium">Rewritten query:</span> {metadata.final_query}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}