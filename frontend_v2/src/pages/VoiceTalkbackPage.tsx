import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Send,
  Bot,
  User,
  Volume2,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { processVoiceTextApi, processVoiceAudioApi, VoiceProcessResponse } from '../api/voice';
import { useAuth } from '../hooks/useAuth';

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  actionTaken?: string;
  audioBase64?: string;
  timestamp: string;
  details?: any;
}

const SAMPLE_PROMPTS = [
  { label: 'Check Payment', prompt: 'Payment aaya kya?' },
  { label: 'Record Sale (2 Chai ₹40)', prompt: '2 chai 40 rupaye' },
  { label: 'Add Item to Menu', prompt: 'Menu mein burger add karo 100 rupaye' },
  { label: 'Query Receivables', prompt: 'Kitna pending udhaar hai?' },
  { label: 'List Catalog Items', prompt: 'Catalog batao kitne items hain' },
];

export const VoiceTalkbackPage: React.FC = () => {
  const { merchant } = useAuth();

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: `Namaste ${merchant?.name || 'Shopkeeper'}! Main VoiceLedger AI Assistant hoon. Aap bolkar sale record karwa sakte hain, payment status check kar sakte hain, ya catalog me item add kar sakte hain.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [inputText, setInputText] = useState<string>('');
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [activeLang, setActiveLang] = useState<'hi-IN' | 'en-IN'>('hi-IN');
  const [webSpeechSupported, setWebSpeechSupported] = useState<boolean>(true);

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition();
      recognizer.continuous = false;
      recognizer.interimResults = false;
      recognizer.lang = activeLang;

      recognizer.onstart = () => setIsListening(true);
      recognizer.onend = () => setIsListening(false);
      recognizer.onerror = (e: any) => {
        console.warn('Speech recognition notice:', e.error);
        setIsListening(false);
      };

      recognizer.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          handleSendCommand(transcript);
        }
      };

      recognitionRef.current = recognizer;
    } else {
      setWebSpeechSupported(false);
    }
  }, [activeLang]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const playAudio = (audioBase64?: string, fallbackText?: string) => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }

    if (audioBase64) {
      try {
        const audio = new Audio(audioBase64);
        currentAudioRef.current = audio;
        audio.play().catch((err) => console.warn('Audio play notice:', err));
        return;
      } catch (err) {
        console.warn('Audio playback error:', err);
      }
    }

    // Web SpeechSynthesis fallback
    if (fallbackText && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(fallbackText);
      utterance.lang = activeLang;
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleToggleVoice = async () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    // Start recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.lang = activeLang;
        recognitionRef.current.start();
      } catch (err) {
        console.warn('Recognition start notice:', err);
      }
    } else {
      // Fallback to MediaRecorder upload
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        audioChunksRef.current = [];

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunksRef.current.push(e.data);
        };

        recorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          stream.getTracks().forEach((t) => t.stop());
          await handleSendAudioBlob(audioBlob);
        };

        mediaRecorderRef.current = recorder;
        recorder.start();
        setIsListening(true);
      } catch (err: any) {
        alert(`Microphone permission needed: ${err.message}`);
      }
    }
  };

  const handleSendAudioBlob = async (blob: Blob) => {
    setIsProcessing(true);
    const userMsg: Message = {
      id: String(Date.now()),
      sender: 'user',
      text: '🎙️ Spoken audio command...',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const resp: VoiceProcessResponse = await processVoiceAudioApi(blob);
      const agentMsg: Message = {
        id: String(Date.now() + 1),
        sender: 'agent',
        text: resp.agent_reply || 'Command processed.',
        actionTaken: resp.action_taken,
        audioBase64: resp.audio_base64,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        details: resp,
      };
      setMessages((prev) => [...prev, agentMsg]);
      playAudio(resp.audio_base64, resp.agent_reply);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          sender: 'agent',
          text: `Error processing audio: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendCommand = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isProcessing) return;

    setInputText('');
    setIsProcessing(true);

    const userMsg: Message = {
      id: String(Date.now()),
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const resp: VoiceProcessResponse = await processVoiceTextApi(
        trimmed,
        activeLang === 'hi-IN' ? 'hi' : 'en',
        true
      );

      const agentMsg: Message = {
        id: String(Date.now() + 1),
        sender: 'agent',
        text: resp.agent_reply || 'Command processed.',
        actionTaken: resp.action_taken,
        audioBase64: resp.audio_base64,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        details: resp,
      };

      setMessages((prev) => [...prev, agentMsg]);
      playAudio(resp.audio_base64, resp.agent_reply);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          sender: 'agent',
          text: `Error: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header Bar */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row justify-between sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Voice Talkback Assistant</h1>
            <span className="text-2xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-blue-600" />
              AI Agent Active
            </span>
            <span
              className={`text-3xs font-medium px-2 py-0.5 rounded border ${
                webSpeechSupported
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              {webSpeechSupported ? 'Web Speech API' : 'Audio Stream Mode'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Hands-free natural language shopkeeper assistant for sales entry, payment verification, and menu setup.
          </p>
        </div>

        {/* Language Toggle */}
        <div className="inline-flex bg-slate-100 p-1 rounded-xl gap-1 text-2xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveLang('hi-IN')}
            className={`px-3 py-1 rounded-lg transition ${
              activeLang === 'hi-IN' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🇮🇳 Hindi (हिन्दी)
          </button>
          <button
            type="button"
            onClick={() => setActiveLang('en-IN')}
            className={`px-3 py-1 rounded-lg transition ${
              activeLang === 'en-IN' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🇬🇧 English (India)
          </button>
        </div>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-2xs font-medium">
        <span className="text-slate-400 font-bold uppercase tracking-wider text-3xs whitespace-nowrap">
          Try saying:
        </span>
        {SAMPLE_PROMPTS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => handleSendCommand(p.prompt)}
            className="px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition whitespace-nowrap shadow-2xs"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Chat Conversation Area */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xs flex flex-col h-[520px] overflow-hidden">
        {/* Messages Stream */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                }`}
              >
                {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`max-w-[80%] rounded-2xl p-4 text-xs shadow-2xs space-y-2 ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-xs'
                    : 'bg-slate-50 border border-slate-200 text-slate-800 rounded-tl-xs'
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <span
                    className={`font-semibold text-2xs ${
                      msg.sender === 'user' ? 'text-blue-100' : 'text-slate-500'
                    }`}
                  >
                    {msg.sender === 'user' ? 'You' : 'VoiceLedger Agent'}
                  </span>
                  <span
                    className={`text-3xs ${
                      msg.sender === 'user' ? 'text-blue-200' : 'text-slate-400'
                    }`}
                  >
                    {msg.timestamp}
                  </span>
                </div>

                <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>

                {/* Agent Action Badge & Audio Button */}
                {msg.sender === 'agent' && (
                  <div className="flex items-center justify-between pt-1 border-t border-slate-200/60">
                    {msg.actionTaken ? (
                      <span className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                        <CheckCircle2 className="w-3 h-3 text-blue-600" />
                        {msg.actionTaken}
                      </span>
                    ) : (
                      <span />
                    )}

                    <button
                      type="button"
                      onClick={() => playAudio(msg.audioBase64, msg.text)}
                      className="inline-flex items-center gap-1 text-2xs font-medium text-slate-600 hover:text-blue-700 p-1 rounded hover:bg-slate-100 transition"
                      title="Listen again"
                    >
                      <Volume2 className="w-3.5 h-3.5 text-blue-600" />
                      Play Voice
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isProcessing && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-500 rounded-tl-xs flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                Thinking and querying store ledger...
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Input Bar & Mic Trigger */}
        <div className="p-4 border-t border-slate-200 bg-slate-50/60 flex items-center gap-3">
          {/* Glowing Voice Trigger Button */}
          <button
            type="button"
            onClick={handleToggleVoice}
            className={`relative w-11 h-11 rounded-full flex items-center justify-center transition shadow-xs ${
              isListening
                ? 'bg-rose-600 text-white animate-pulse ring-4 ring-rose-300'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
            title={isListening ? 'Stop listening' : 'Start speaking'}
          >
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>

          {/* Text input for fallback */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendCommand(inputText);
            }}
            className="flex-1 flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={
                isListening
                  ? 'Listening to microphone... Speak now...'
                  : 'Speak into mic or type command (e.g. "Payment check karo")...'
              }
              className={`flex-1 px-4 py-2.5 rounded-xl border text-xs focus:outline-hidden focus:ring-2 focus:ring-blue-500 ${
                isListening
                  ? 'bg-rose-50 border-rose-300 text-rose-800 font-semibold animate-pulse'
                  : 'bg-white border-slate-200 text-slate-800'
              }`}
            />

            <button
              type="submit"
              disabled={isProcessing || !inputText.trim()}
              className="p-2.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 transition disabled:opacity-40"
              title="Send text"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
