export default function TypingIndicator() {
  return (
    <div className="flex items-center gap-1">
      <span className="text-sm text-gray-500 mr-2">Feldolgozás</span>
      <div className="flex gap-1">
        <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
        <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
        <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
      </div>
    </div>
  );
}
