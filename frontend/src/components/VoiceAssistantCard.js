import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Platform,
  ScrollView,
} from 'react-native';
import { Mic, MicOff, Send, Bot, Sparkles, Volume2 } from 'lucide-react-native';
import { colors } from '../theme/colors';
import { voiceService } from '../services/voiceService';
import { apiService } from '../services/apiService';

const SAMPLE_PROMPTS = [
  { label: '🔍 Payment aaya kya?', prompt: 'Payment aaya kya?' },
  { label: '➕ Menu me Burger (₹100) add karo', prompt: 'Menu mein burger add karo 100 rupaye' },
  { label: '☕ 2 Coffee + Sandwich (₹120)', prompt: '2 coffee aur 1 sandwich 120 rupaye' },
  { label: '📚 3 Notebook (₹150)', prompt: '3 notebook 150 rs' },
  { label: '❓ Kitna pending hai?', prompt: 'Kitna pending hai?' },
];

export default function VoiceAssistantCard({ onActionComplete }) {
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentResponse, setAgentResponse] = useState(null);

  // Pulse animation for recording
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (isRecording) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.25,
            duration: 700,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 700,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  useEffect(() => {
    // Initialize Web Speech API if in web browser
    voiceService.initWebSpeech(
      (transcript) => {
        setInputText(transcript);
        handleSendVoice(transcript);
      },
      () => setIsRecording(true),
      () => setIsRecording(false),
      () => setIsRecording(false)
    );
  }, []);

  const toggleRecording = () => {
    if (isRecording) {
      voiceService.stopListening();
      setIsRecording(false);
    } else {
      if (Platform.OS === 'web') {
        voiceService.startListening();
      } else {
        // Fallback for mobile native without Speech API: hint user
        setIsRecording(!isRecording);
      }
    }
  };

  const handleSendVoice = async (overrideText = null) => {
    const query = (overrideText || inputText).trim();
    if (!query || isProcessing) return;

    setIsProcessing(true);
    setAgentResponse({
      reply: 'VoiceLedger Agent is analyzing and checking...',
      action: 'Processing',
      status: 'loading',
    });

    try {
      const data = await apiService.processVoiceCommand(query);
      
      setAgentResponse({
        reply: data.agent_reply || 'Completed.',
        action: data.action_taken || 'Completed',
        audioBase64: data.audio_base64,
        status: 'success',
      });

      // Play neural voice audio
      if (data.audio_base64 || data.agent_reply) {
        voiceService.playTTSAudio(data.audio_base64, data.agent_reply);
      }

      setInputText('');
      if (onActionComplete) onActionComplete();
    } catch (err) {
      setAgentResponse({
        reply: `Error: ${err.message}`,
        action: 'Failed',
        status: 'error',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <View style={styles.cardContainer}>
      {/* Header Row */}
      <View style={styles.headerRow}>
        <View style={styles.titleWrap}>
          <Text style={styles.cardIcon}>🎙️</Text>
          <View>
            <Text style={styles.cardTitle}>Speak or Check Payment Arrival</Text>
            <Text style={styles.cardSubtitle}>
              Speak sold products or ask: <Text style={{ fontStyle: 'italic', color: '#c7d2fe' }}>"Payment aaya kya?"</Text>
            </Text>
          </View>
        </View>

        {/* Big Animated Mic Button */}
        <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
          <TouchableOpacity
            style={[styles.micBtn, isRecording && styles.micBtnActive]}
            onPress={toggleRecording}
            activeOpacity={0.8}
          >
            {isRecording ? (
              <MicOff size={28} color="#ffffff" strokeWidth={2.5} />
            ) : (
              <Mic size={28} color="#ffffff" strokeWidth={2.5} />
            )}
          </TouchableOpacity>
        </Animated.View>
      </View>

      {/* Input Row */}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder={
            isRecording
              ? 'Listening... Speak now!'
              : 'Speak a sale (e.g. 2 coffee 60 rupaye) or ask: Payment aaya kya?...'
          }
          placeholderTextColor={colors.textMuted}
          onSubmitEditing={() => handleSendVoice()}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!inputText.trim() || isProcessing) && styles.sendBtnDisabled]}
          onPress={() => handleSendVoice()}
          disabled={!inputText.trim() || isProcessing}
          activeOpacity={0.8}
        >
          {isProcessing ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <>
              <Text style={styles.sendBtnText}>Process</Text>
              <Send size={16} color="#ffffff" style={{ marginLeft: 6 }} />
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* Quick Prompt Chips */}
      <View style={styles.chipsContainer}>
        <Text style={styles.chipsLabel}>Quick Actions:</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsScroll}>
          {SAMPLE_PROMPTS.map((item, index) => (
            <TouchableOpacity
              key={index}
              style={[styles.chip, index === 0 && styles.chipHighlight]}
              onPress={() => {
                setInputText(item.prompt);
                handleSendVoice(item.prompt);
              }}
              activeOpacity={0.7}
            >
              <Text style={[styles.chipText, index === 0 && styles.chipTextHighlight]}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Live Agent Response Banner */}
      {agentResponse && (
        <View style={styles.responseBox}>
          <View style={styles.botIconWrap}>
            <Bot size={22} color={colors.primary} />
          </View>
          <View style={styles.responseContent}>
            <View style={styles.responseHeader}>
              <Text style={styles.agentName}>VoiceLedger Agent</Text>
              <View style={styles.actionTag}>
                <Text style={styles.actionTagText}>{agentResponse.action}</Text>
              </View>
            </View>
            <Text style={styles.agentReplyText}>{agentResponse.reply}</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  cardContainer: {
    backgroundColor: colors.bgCard,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
    marginBottom: 24,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 8,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 16,
  },
  cardIcon: {
    fontSize: 28,
    marginRight: 12,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    letterSpacing: -0.3,
  },
  cardSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  micBtn: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 12,
    elevation: 8,
  },
  micBtnActive: {
    backgroundColor: colors.accentRose,
    shadowColor: colors.accentRose,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  textInput: {
    flex: 1,
    backgroundColor: 'rgba(10, 14, 23, 0.7)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: colors.textPrimary,
    fontSize: 14,
  },
  sendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 12,
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    opacity: 0.5,
  },
  sendBtnText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 14,
  },
  chipsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  chipsLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
    marginRight: 10,
  },
  chipsScroll: {
    flexDirection: 'row',
    gap: 8,
  },
  chip: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  chipHighlight: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderColor: 'rgba(99, 102, 241, 0.35)',
  },
  chipText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  chipTextHighlight: {
    color: '#a5b4fc',
    fontWeight: '600',
  },
  responseBox: {
    marginTop: 20,
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.25)',
    borderRadius: 14,
    padding: 16,
    flexDirection: 'row',
  },
  botIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  responseContent: {
    flex: 1,
  },
  responseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  agentName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#a5b4fc',
  },
  actionTag: {
    backgroundColor: 'rgba(99, 102, 241, 0.25)',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  actionTagText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#e0e7ff',
    textTransform: 'uppercase',
  },
  agentReplyText: {
    fontSize: 14,
    color: colors.textPrimary,
    lineHeight: 20,
  },
});
