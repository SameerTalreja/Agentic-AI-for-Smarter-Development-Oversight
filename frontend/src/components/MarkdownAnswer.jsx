import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownAnswer({ content }) {
  return (
    <div className="markdown-answer">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}