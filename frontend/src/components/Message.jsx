// frontend/src/components/Message.jsx
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ChevronDown, ChevronUp, BrainCircuit, User } from 'lucide-react'

export default function Message({ role, content, metadata, isUploading = false }) {
  const [showDetails, setShowDetails] = useState(false)

  // System / status messages (upload progress, errors)
  if (role === 'system') {
    return (
      <div className="flex justify-center my-1">
        <div className="inline-flex items-center gap-1.5 bg-[#2f2f2f] text-[#8e8ea0] text-xs px-3 py-1.5 rounded-full">
          {isUploading && (
            <span className="w-2.5 h-2.5 border-2 border-[#8e8ea0] border-t-transparent rounded-full animate-spin" />
          )}
          <span>{content}</span>
        </div>
      </div>
    )
  }

  // User messages — right-aligned bubble
  if (role === 'user') {
    return (
      <div className="flex justify-end gap-2 py-2">
        <div className="max-w-[80%] bg-[#2f2f2f] text-[#ececec] rounded-2xl px-4 py-2.5 text-sm leading-relaxed">
          {content}
        </div>
        <div className="w-7 h-7 rounded-full bg-[#3d3d3d] flex items-center justify-center shrink-0 mt-0.5">
          <User size={14} className="text-[#ececec]" />
        </div>
      </div>
    )
  }

  // Assistant messages — left-aligned plain text
  return (
    <div className="flex gap-3 py-2">
      <div className="w-7 h-7 rounded-full bg-[#2f2f2f] flex items-center justify-center shrink-0 mt-0.5">
        <BrainCircuit size={14} className="text-white" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="prose prose-sm prose-invert max-w-none text-[#ececec]
          prose-p:leading-relaxed prose-p:my-1
          prose-pre:bg-[#2f2f2f] prose-pre:text-[#ececec]
          prose-code:bg-[#2f2f2f] prose-code:px-1 prose-code:rounded prose-code:text-[#ececec]
          prose-headings:text-[#ececec] prose-strong:text-[#ececec]
          prose-li:my-0.5">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>

        {metadata && (
          <div className="mt-3">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-[#8e8ea0] text-xs hover:text-[#ececec] transition-colors"
            >
              {showDetails ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {showDetails ? 'Hide details' : 'Show details'}
            </button>

            {showDetails && (
              <div className="mt-2 text-xs text-[#8e8ea0] space-y-1 bg-[#2f2f2f] p-3 rounded-lg">
                <div><span className="text-[#ececec]">Loop count:</span> {metadata.loop_count}</div>
                <div>
                  <span className="text-[#ececec]">Critic score:</span>{' '}
                  {metadata.critic_score != null ? metadata.critic_score.toFixed(2) : 'N/A'}
                </div>
                <div><span className="text-[#ececec]">Critic reason:</span> {metadata.critic_reason || 'N/A'}</div>
                <div><span className="text-[#ececec]">Latency:</span> {metadata.total_latency_ms} ms</div>
                <div><span className="text-[#ececec]">Chunks used:</span> {metadata.chunks_used}</div>
                {metadata.final_query !== metadata.original_query && (
                  <div><span className="text-[#ececec]">Rewritten query:</span> {metadata.final_query}</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
