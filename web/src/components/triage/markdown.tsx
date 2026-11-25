import ReactMarkdown from "react-markdown";

// Raw HTML in the text is not rendered (react-markdown's default), so LLM output cannot inject markup.
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        h1: ({ children }) => <h3 className="mt-5 mb-1.5 text-base font-semibold">{children}</h3>,
        h2: ({ children }) => <h3 className="mt-5 mb-1.5 text-base font-semibold text-primary">{children}</h3>,
        h3: ({ children }) => <h4 className="mt-4 mb-1 text-sm font-semibold">{children}</h4>,
        p: ({ children }) => <p className="my-2 text-sm leading-relaxed">{children}</p>,
        ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 text-sm">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 text-sm">{children}</ol>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
