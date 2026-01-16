import React, { useState } from 'react';
import { X, TrendingUp, TrendingDown, Loader2, CheckCircle2 } from 'lucide-react';

const NodeDifficultyDialog = ({ node, userId, onClose, onDifficultyAdjusted }) => {
    const [direction, setDirection] = useState(null); // 'easier' or 'harder'
    const [amount, setAmount] = useState(null); // 'little', 'moderate', 'a_lot'
    const [reason, setReason] = useState(''); // User's reason for adjustment
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [updatedNode, setUpdatedNode] = useState(null);

    const amountOptions = [
        { value: 'little', label: 'A little', description: 'Small adjustment (25%)' },
        { value: 'moderate', label: 'Moderately', description: 'Medium adjustment (50%)' },
        { value: 'a_lot', label: 'A lot', description: 'Large adjustment (75%)' },
    ];

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!direction || !amount) return;

        setIsLoading(true);
        setError(null);

        try {
            const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
            const url = `${backend}/api/skill-tree/node/adjust-difficulty`;
            const payload = {
                user_id: userId || 'user_01',
                node_id: node.id,
                direction: direction,
                amount: amount,
                reason: reason.trim() || null,
            };
            
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'NodeDifficultyDialog.jsx:handleSubmit:pre-fetch',message:'About to make fetch request',data:{url,backend,payload,hasUserId:!!userId,nodeId:node.id,direction,amount,hasReason:!!reason},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H3'})}).catch(()=>{});
            // #endregion
            
            // Create AbortController for timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });
            
            clearTimeout(timeoutId);
            
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'NodeDifficultyDialog.jsx:handleSubmit:post-fetch',message:'Fetch completed',data:{url,status:response.status,statusText:response.statusText,ok:response.ok,headers:Object.fromEntries(response.headers.entries())},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2'})}).catch(()=>{});
            // #endregion

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to adjust difficulty' }));
                // #region agent log
                fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'NodeDifficultyDialog.jsx:handleSubmit:error-response',message:'Response not OK',data:{status:response.status,statusText:response.statusText,errorData},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H4'})}).catch(()=>{});
                // #endregion
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            const data = await response.json();
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'NodeDifficultyDialog.jsx:handleSubmit:success',message:'Request successful',data:{hasUpdatedNode:!!data.updated_node,hasNewNodes:!!data.new_nodes,newNodesCount:data.new_nodes?.length||0,hasSkillTree:!!data.skill_tree},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1'})}).catch(()=>{});
            // #endregion
            setUpdatedNode(data.updated_node);
            setSuccess(true);
            
            if (onDifficultyAdjusted) {
                onDifficultyAdjusted(data);
            }
        } catch (err) {
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'NodeDifficultyDialog.jsx:handleSubmit:catch',message:'Exception caught',data:{errorName:err.name,errorMessage:err.message,errorStack:err.stack,isNetworkError:err.message.includes('fetch')||err.message.includes('Failed to fetch'),isTypeError:err instanceof TypeError,payload},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H3,H4,H5'})}).catch(()=>{});
            // #endregion
            const errorMessage = err.message || 'Failed to adjust difficulty. Please try again.';
            setError(errorMessage);
            console.error('Error adjusting difficulty:', {
                error: err,
                message: errorMessage,
                name: err.name,
                stack: err.stack,
                payload: payload
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        if (success && onDifficultyAdjusted) {
            // Small delay to show success state
            setTimeout(() => {
                onClose();
            }, 1500);
        } else {
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm p-2" onClick={handleClose}>
            <div 
                className="bg-white rounded-lg shadow-2xl w-full max-w-md max-h-[70vh] flex flex-col mx-2 overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header - Fixed */}
                <div className="flex items-center justify-between p-3 border-b border-slate-200 flex-shrink-0">
                    <div className="min-w-0 pr-2">
                        <h2 className="text-base font-bold text-slate-800 truncate">Adjust Difficulty: {node.name}</h2>
                        <p className="text-xs text-slate-500 mt-0.5 capitalize">{node.type}</p>
                    </div>
                    <button
                        onClick={handleClose}
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0"
                        disabled={isLoading}
                    >
                        <X size={18} className="text-slate-500" />
                    </button>
                </div>

                {/* Current Difficulty Info - Fixed */}
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex-shrink-0">
                    <div className="text-xs text-slate-700">
                        <span className="font-medium">Current:</span> {node.required_completions || 30} completions required
                    </div>
                    {node.description && (
                        <p className="text-xs text-slate-600 mt-1 italic line-clamp-1">"{node.description}"</p>
                    )}
                </div>

                {/* Content - Scrollable */}
                <div className="p-3 overflow-y-auto flex-1 min-h-0">
                    {success ? (
                        <div className="text-center py-4">
                            <CheckCircle2 size={40} className="mx-auto text-green-500 mb-2" />
                            <h3 className="text-sm font-semibold text-slate-800 mb-2">Difficulty Adjusted!</h3>
                            {updatedNode && (
                                <div className="mt-3 p-2 bg-blue-50 rounded-lg border border-blue-100">
                                    <p className="text-xs font-medium text-slate-700 mb-1">New: {updatedNode.name}</p>
                                    <p className="text-xs text-slate-600">{updatedNode.required_completions} completions required</p>
                                </div>
                            )}
                            <p className="text-xs text-slate-500 mt-3">Closing automatically...</p>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-3">
                            {/* Direction Selection */}
                            <div>
                                <label className="block text-xs font-medium text-slate-700 mb-2">
                                    Make it:
                                </label>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setDirection('easier')}
                                        className={`p-2.5 border-2 rounded-lg transition-all flex flex-col items-center gap-1 ${
                                            direction === 'easier'
                                                ? 'border-green-500 bg-green-50'
                                                : 'border-slate-200 hover:border-slate-300'
                                        }`}
                                        disabled={isLoading}
                                    >
                                        <TrendingDown size={18} className={direction === 'easier' ? 'text-green-600' : 'text-slate-400'} />
                                        <span className="font-medium text-slate-700 text-xs">Easier</span>
                                        <span className="text-[10px] text-slate-500">Reduce difficulty</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setDirection('harder')}
                                        className={`p-2.5 border-2 rounded-lg transition-all flex flex-col items-center gap-1 ${
                                            direction === 'harder'
                                                ? 'border-red-500 bg-red-50'
                                                : 'border-slate-200 hover:border-slate-300'
                                        }`}
                                        disabled={isLoading}
                                    >
                                        <TrendingUp size={18} className={direction === 'harder' ? 'text-red-600' : 'text-slate-400'} />
                                        <span className="font-medium text-slate-700 text-xs">Harder</span>
                                        <span className="text-[10px] text-slate-500">Increase difficulty</span>
                                    </button>
                                </div>
                            </div>

                            {/* Reason Input - Show after direction is selected */}
                            {direction && (
                                <div>
                                    <label className="block text-xs font-medium text-slate-700 mb-1.5">
                                        Why {direction === 'easier' ? 'easier' : 'harder'}?
                                        <span className="text-slate-500 font-normal ml-1">(Optional)</span>
                                    </label>
                                    <textarea
                                        value={reason}
                                        onChange={(e) => setReason(e.target.value)}
                                        placeholder="e.g., I can already do this easily..."
                                        className="w-full p-2 border-2 border-slate-200 rounded-lg resize-none focus:outline-none focus:border-blue-500 transition-colors text-xs"
                                        rows={2}
                                        disabled={isLoading}
                                    />
                                    <p className="text-[10px] text-slate-500 mt-0.5">
                                        Context helps us create better solutions.
                                    </p>
                                </div>
                            )}

                            {/* Amount Selection */}
                            {direction && (
                                <div>
                                    <label className="block text-xs font-medium text-slate-700 mb-2">
                                        How much {direction === 'easier' ? 'easier' : 'harder'}?
                                    </label>
                                    <div className="space-y-1.5">
                                        {amountOptions.map((option) => (
                                            <button
                                                key={option.value}
                                                type="button"
                                                onClick={() => setAmount(option.value)}
                                                className={`w-full p-2 border-2 rounded-lg transition-all text-left ${
                                                    amount === option.value
                                                        ? 'border-blue-500 bg-blue-50'
                                                        : 'border-slate-200 hover:border-slate-300'
                                                }`}
                                                disabled={isLoading}
                                            >
                                                <div className="font-medium text-slate-700 text-xs">{option.label}</div>
                                                <div className="text-[10px] text-slate-500">{option.description}</div>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Preview */}
                            {direction && amount && (
                                <div className="p-2 bg-blue-50 rounded-lg border border-blue-100">
                                    <p className="text-xs font-medium text-slate-700 mb-0.5">Preview:</p>
                                    <p className="text-[10px] text-slate-600">
                                        {direction === 'easier' ? 'Decreasing' : 'Increasing'} by{' '}
                                        {amount === 'little' ? '25%' : amount === 'moderate' ? '50%' : '75%'}
                                        . Will regenerate.
                                    </p>
                                </div>
                            )}

                            {error && (
                                <div className="p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                                    {error}
                                </div>
                            )}

                            {/* Footer buttons */}
                            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 mt-3">
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                                    disabled={isLoading}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isLoading || !direction || !amount}
                                    className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 size={14} className="animate-spin" />
                                            Adjusting...
                                        </>
                                    ) : (
                                        'Apply'
                                    )}
                                </button>
                            </div>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NodeDifficultyDialog;
