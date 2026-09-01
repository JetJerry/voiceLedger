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
import { Mic, MicOff, Send, Bot, CheckCircle2 } from 'lucide-react-native';
import { colors } from '../theme/colors';
import { voiceService } from '../services/voiceService';
import { apiService } from '../services/apiService';

const SAMPLE_PROMPTS = [
  { label: 'Check Payment Status', prompt: 'Payment aaya kya?' },
  { label: 'Add Burger (₹100)', prompt: 'Menu mein burger add karo 100 rupaye' },
  { label: '2 Coffee + Sandwich (₹120)', prompt: '2 coffee aur 1 sandwich 120 rupaye' },
  { label: '3 Notebooks (₹150)', prompt: '3 notebook 150 rs' },
  { label: 'Pending Receivables', prompt: 'Kitna pending hai?' },
];

export default function VoiceAssistantCard({ onActionComplete }) {
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentResponse, setAgentResponse] = useState(null);

  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (isRecording) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.15,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  useEffect(() => {
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
        setIsRecording(!isRecording);
      }
    }
  };

  const handleSendVoice = async (overrideText = null) => {
    const query = (overrideText || inputText).trim();
    if (!query || isProcessing) return;

    setIsProcessing(true);
    setAgentResponse({
      reply: 'Processing query...',
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
          <View style={styles.iconBadge}>
            <Mic size={18} color="#ffffff" strokeWidth={2.2} />
          </View>
          <View>
            <Text style={styles.cardTitle}>Voice Transaction & Settlement Terminal</Text>
            <Text style={styles.cardSubtitle}>
              Speak sales entries or ask: <Text style={{ fontStyle: 'italic', color: colors.primary }}>"Payment aaya kya?"</Text>
            </Text>
          </View>
        </View>

        {/* Mic Action Button */}
        <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
          <TouchableOpacity
            style={[styles.micBtn, isRecording && styles.micBtnActive]}
            onPress={toggleRecording}
            activeOpacity={0.8}
            accessibilityLabel={isRecording ? "Stop voice listening" : "Start voice listening"}
          >
            {isRecording ? (
              <MicOff size={22} color="#ffffff" strokeWidth={2.2} />
            ) : (
              <Mic size={22} color="#ffffff" strokeWidth={2.2} />
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
              ? 'Listening... Speak clearly into microphone'
              : 'Type or speak command (e.g. 2 coffee 60 rs, or Payment aaya kya?)...'
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
              <Text style={styles.sendBtnText}>Execute</Text>
              <Send size={14} color="#ffffff" style={{ marginLeft: 6 }} />
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* Quick Action Chips */}
      <View style={styles.chipsContainer}>
        <Text style={styles.chipsLabel}>Suggestions:</Text>
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
            <Bot size={18} color={colors.primary} />
          </View>
          <View style={styles.responseContent}>
            <View style={styles.responseHeader}>
              <Text style={styles.agentName}>AI Assistant</Text>
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
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 22,
    marginBottom: 20,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 16,
  },
  iconBadge: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
    letterSpacing: -0.2,
  },
  cardSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  micBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  micBtnActive: {
    backgroundColor: colors.accentRose,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
  },
  textInput: {
    flex: 1,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 13,
  },
  sendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    opacity: 0.5,
  },
  sendBtnText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 13,
  },
  chipsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  chipsLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
    marginRight: 8,
  },
  chipsScroll: {
    flexDirection: 'row',
    gap: 6,
  },
  chip: {
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  chipHighlight: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderColor: 'rgba(99, 102, 241, 0.3)',
  },
  chipText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  chipTextHighlight: {
    color: colors.primary,
    fontWeight: '600',
  },
  responseBox: {
    marginTop: 16,
    backgroundColor: 'rgba(99, 102, 241, 0.06)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.2)',
    borderRadius: 10,
    padding: 14,
    flexDirection: 'row',
  },
  botIconWrap: {
    width: 30,
    height: 30,
    borderRadius: 6,
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  responseContent: {
    flex: 1,
  },
  responseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  agentName: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.primary,
  },
  actionTag: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  actionTagText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#e0e7ff',
    textTransform: 'uppercase',
  },
  agentReplyText: {
    fontSize: 13,
    color: colors.textPrimary,
    lineHeight: 18,
  },
});
