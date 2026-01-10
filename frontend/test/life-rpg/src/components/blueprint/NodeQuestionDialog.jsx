import React, { useState } from 'react';
import { X, Send, Loader2 } from 'lucide-react';

const NodeQuestionDialog = ({ node, userId, onClose, onQuestionAnswered }) => {
    const [question, setQuestion] = useState('');
    const [answer, setAnswer] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!question.trim()) return;

        setIsLoading(true);
        setError(null);

        try {
            const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
            const response = await fetch(`${backend}/api/skill-tree/node/question`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId || 'user_01',
                    node_id: node.id,
                    question: question.trim(),
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to get answer' }));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            const data = await response.json();
            setAnswer(data.answer);
            if (onQuestionAnswered) {
                onQuestionAnswered(data);
            }
        } catch (err) {
            setError(err.message || 'Failed to get answer. Please try again.');
            console.error('Error asking question:', err);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
            <div 
                className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col mx-4"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-200">
                    <div>
                        <h2 className="text-xl font-bold text-slate-800">Ask About: {node.name}</h2>
                        <p className="text-sm text-slate-500 mt-1 capitalize">{node.type}</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                    >
                        <X size={20} className="text-slate-500" />
                    </button>
                </div>

                {/* Node Info */}
                {node.description && (
                    <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
                        <p className="text-sm text-slate-700 italic">"{node.description}"</p>
                        {node.required_completions && (
                            <p className="text-xs text-slate-500 mt-2">
                                Required completions: {node.required_completions}
                            </p>
                        )}
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {!answer ? (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label htmlFor="question" className="block text-sm font-medium text-slate-700 mb-2">
                                    What would you like to know?
                                </label>
                                <textarea
                                    id="question"
                                    value={question}
                                    onChange={(e) => setQuestion(e.target.value)}
                                    placeholder="e.g., How do I complete this? What does this mean? What should I focus on?"
                                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                                    rows={4}
                                    disabled={isLoading}
                                />
                            </div>

                            {error && (
                                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                                    {error}
                                </div>
                            )}

                            <div className="flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                                    disabled={isLoading}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isLoading || !question.trim()}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 size={16} className="animate-spin" />
                                            Asking...
                                        </>
                                    ) : (
                                        <>
                                            <Send size={16} />
                                            Ask
                                        </>
                                    )}
                                </button>
                            </div>
                        </form>
                    ) : (
                        <div className="space-y-4">
                            <div>
                                <h3 className="text-sm font-semibold text-slate-600 mb-2">Your Question:</h3>
                                <p className="text-sm text-slate-800 bg-slate-50 p-3 rounded-lg italic">
                                    "{question}"
                                </p>
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-slate-600 mb-2">Answer:</h3>
                                <div className="text-sm text-slate-700 bg-blue-50 p-4 rounded-lg border border-blue-100 whitespace-pre-wrap">
                                    {answer}
                                </div>
                            </div>
                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    onClick={() => {
                                        setAnswer(null);
                                        setQuestion('');
                                        setError(null);
                                    }}
                                    className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                                >
                                    Ask Another Question
                                </button>
                                <button
                                    onClick={onClose}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                                >
                                    Close
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NodeQuestionDialog;
