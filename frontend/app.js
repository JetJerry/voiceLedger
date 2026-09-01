import React, { useState, useEffect, useCallback } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  StatusBar,
  RefreshControl,
  useWindowDimensions,
  Platform,
} from 'react-native';
import { Volume2, Receipt, Package, ArrowRight, X } from 'lucide-react-native';
import { colors } from './src/theme/colors';
import { apiService } from './src/services/apiService';
import { voiceService } from './src/services/voiceService';
import Header from './src/components/Header';
import LoginScreen from './src/components/LoginScreen';
import VoiceAssistantCard from './src/components/VoiceAssistantCard';
import MetricsGrid from './src/components/MetricsGrid';
import SalesLedger from './src/components/SalesLedger';
import CatalogManager from './src/components/CatalogManager';
import PaymentSimModal from './src/components/PaymentSimModal';
import AdminDashboard from './src/components/AdminDashboard';

export default function App() {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  // Authentication State
  const [currentUser, setCurrentUser] = useState(null); // { id, name, username, role, business_type }
  const [currentView, setCurrentView] = useState('terminal'); // 'terminal' | 'sales' | 'catalog' | 'admin'
  const [summaryData, setSummaryData] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeSimSale, setActiveSimSale] = useState(null);
  const [isSimSubmitting, setIsSimSubmitting] = useState(false);

  // Live Payment Soundbox Announcement State
  const [soundboxAlert, setSoundboxAlert] = useState(null);

  // Restore session on app load
  useEffect(() => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const raw = window.localStorage.getItem('voiceledger_session');
        if (raw) {
          const session = JSON.parse(raw);
          if (session?.user && session?.role) {
            setCurrentUser(session.user);
            setCurrentView(session.role === 'admin' ? 'admin' : 'terminal');
          }
        }
      }
    } catch (e) {
      console.warn('Session restore note:', e);
    }
  }, []);

  // Fetch Dashboard summary & active merchant
  const loadDashboard = useCallback(async () => {
    if (!currentUser) return;
    try {
      const data = await apiService.getDashboardSummary();
      setSummaryData(data);
    } catch (e) {
      console.warn('Dashboard fetch notice:', e.message);
    }
  }, [currentUser]);

  // Poll for Live Payment Arrival Announcements (Soundbox mode)
  const pollPaymentAnnouncements = useCallback(async () => {
    if (!currentUser || currentUser.role === 'admin') return;
    try {
      const announcements = await apiService.getPaymentAnnouncements(currentUser.id);
      if (announcements && announcements.length > 0) {
        for (const ann of announcements) {
          // Set visual alert
          setSoundboxAlert(ann);
          // Play Neural TTS Voice Announcement aloud
          if (ann.audio_base64 || ann.speech_text) {
            voiceService.playTTSAudio(ann.audio_base64, ann.speech_text);
          }
          // Acknowledge so it is not repeated
          await apiService.acknowledgePaymentAnnouncement(ann.id);
          // Refresh metrics & ledger
          await loadDashboard();
        }
      }
    } catch (e) {
      // Background poll notice
    }
  }, [currentUser, loadDashboard]);

  const handleLoginSuccess = (user, role, token) => {
    setCurrentUser(user);
    setCurrentView(role === 'admin' ? 'admin' : 'terminal');
    loadDashboard();
  };

  const handleLogout = () => {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.removeItem('voiceledger_session');
    }
    setCurrentUser(null);
    setSummaryData(null);
    setCurrentView('terminal');
    setSoundboxAlert(null);
  };

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await loadDashboard();
    setIsRefreshing(false);
  };

  useEffect(() => {
    if (!currentUser) return;
    loadDashboard();
    pollPaymentAnnouncements();

    // Auto-refresh summary & poll payment soundbox every 3 seconds
    const interval = setInterval(() => {
      loadDashboard();
      pollPaymentAnnouncements();
    }, 3000);
    return () => clearInterval(interval);
  }, [currentUser, loadDashboard, pollPaymentAnnouncements]);

  // Payment simulation handler
  const handleOpenSimulate = (sale) => {
    setActiveSimSale(sale);
  };

  const handleCloseSimulate = () => {
    setActiveSimSale(null);
  };

  const handleSubmitSimPayment = async (saleId, amount) => {
    setIsSimSubmitting(true);
    try {
      await apiService.simulatePayment(saleId, amount);
      handleCloseSimulate();
      await loadDashboard();
      await pollPaymentAnnouncements();
    } catch (e) {
      alert(`Simulation failed: ${e.message}`);
    } finally {
      setIsSimSubmitting(false);
    }
  };

  // If not logged in, render the Login / Portal Selection Screen
  if (!currentUser) {
    return <LoginScreen onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <SafeAreaView style={styles.rootContainer}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Fixed App Header with Nav Tabs & Logout */}
      <Header
        onRefresh={loadDashboard}
        currentView={currentView}
        onSelectView={setCurrentView}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Live Payment Soundbox Announcement Alert Banner */}
      {soundboxAlert && (
        <View style={styles.soundboxBanner}>
          <View style={styles.soundboxLeft}>
            <View style={styles.soundboxIconBadge}>
              <Volume2 size={16} color="#34d399" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.soundboxTitle}>
                Payment Settled: ₹{soundboxAlert.amount} for {soundboxAlert.items_summary}
              </Text>
              <Text style={styles.soundboxSpeech}>{soundboxAlert.speech_text}</Text>
            </View>
          </View>
          <View style={styles.soundboxActions}>
            <TouchableOpacity
              style={styles.soundboxReplayBtn}
              onPress={() => voiceService.playTTSAudio(soundboxAlert.audio_base64, soundboxAlert.speech_text)}
              activeOpacity={0.8}
            >
              <Volume2 size={13} color="#ffffff" style={{ marginRight: 4 }} />
              <Text style={styles.soundboxReplayText}>Replay Voice</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.soundboxDismissBtn}
              onPress={() => setSoundboxAlert(null)}
              activeOpacity={0.7}
            >
              <X size={14} color="#e2e8f0" />
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Main Content Area */}
      <ScrollView
        style={styles.scrollContainer}
        contentContainerStyle={[
          styles.scrollContent,
          isMobile ? styles.scrollContentMobile : styles.scrollContentDesktop,
        ]}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleManualRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
          />
        }
      >
        {/* PAGE 1: Simple, Clean Voice Dashboard */}
        {currentView === 'terminal' && (
          <View style={styles.pageWrap}>
            {/* Hero Voice Assistant Card */}
            <VoiceAssistantCard onActionComplete={loadDashboard} />

            {/* Quick Metrics Overview */}
            <MetricsGrid summary={summaryData} />

            {/* Quick Navigation Cards */}
            <View style={[styles.quickNavRow, isMobile && styles.quickNavRowMobile]}>
              <TouchableOpacity
                style={styles.quickNavCard}
                onPress={() => setCurrentView('sales')}
                activeOpacity={0.8}
              >
                <View style={styles.quickNavIconWrap}>
                  <Receipt size={20} color={colors.primary} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.quickNavTitle}>Sales & Payment Settlement Ledger</Text>
                  <Text style={styles.quickNavSub}>
                    View {summaryData?.total_transactions || 0} recorded orders, track live settlements, and verify payment links.
                  </Text>
                </View>
                <ArrowRight size={18} color={colors.primary} />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.quickNavCard}
                onPress={() => setCurrentView('catalog')}
                activeOpacity={0.8}
              >
                <View style={[styles.quickNavIconWrap, { backgroundColor: 'rgba(6, 182, 212, 0.12)' }]}>
                  <Package size={20} color={colors.accentCyan} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.quickNavTitle}>Product Catalog & Inventory</Text>
                  <Text style={styles.quickNavSub}>
                    Manage items with dynamic attributes across grocery, pharmacy, food, fashion, and hardware.
                  </Text>
                </View>
                <ArrowRight size={18} color={colors.primary} />
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* PAGE 2: Dedicated Sales & Payments Ledger */}
        {currentView === 'sales' && (
          <View style={styles.pageWrap}>
            <SalesLedger
              sales={summaryData?.recent_sales || []}
              onRefresh={handleManualRefresh}
              onSimulatePayment={handleOpenSimulate}
              isRefreshing={isRefreshing}
            />
          </View>
        )}

        {/* PAGE 3: Dedicated Dynamic Product Catalog & Menu Manager */}
        {currentView === 'catalog' && (
          <View style={styles.pageWrap}>
            <CatalogManager onCatalogUpdated={loadDashboard} />
          </View>
        )}

        {/* PAGE 4: Multi-Store Platform Super Administrator */}
        {currentView === 'admin' && (
          <View style={styles.pageWrap}>
            <AdminDashboard
              onSwitchToTerminal={() => setCurrentView('terminal')}
              onRefreshApp={loadDashboard}
            />
          </View>
        )}

        {/* Global Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            VoiceLedger Enterprise • Razorpay Unified Settlement Engine
          </Text>
        </View>
      </ScrollView>

      {/* Payment Simulation Modal */}
      <PaymentSimModal
        visible={!!activeSimSale}
        sale={activeSimSale}
        onClose={handleCloseSimulate}
        onSubmit={handleSubmitSimPayment}
        isSubmitting={isSimSubmitting}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  rootContainer: {
    flex: 1,
    backgroundColor: colors.bg,
    minHeight: '100vh',
    width: '100%',
  },
  scrollContainer: {
    flex: 1,
  },
  scrollContent: {
    paddingVertical: 20,
    paddingHorizontal: 16,
    alignSelf: 'center',
    width: '100%',
  },
  scrollContentDesktop: {
    maxWidth: 1200,
    paddingHorizontal: 24,
  },
  scrollContentMobile: {
    maxWidth: '100%',
    paddingHorizontal: 14,
  },
  footer: {
    paddingVertical: 18,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
  },
  pageWrap: {
    width: '100%',
  },
  quickNavRow: {
    flexDirection: 'row',
    gap: 14,
    marginBottom: 20,
  },
  quickNavRowMobile: {
    flexDirection: 'column',
    gap: 10,
  },
  quickNavCard: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 16,
  },
  quickNavIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 8,
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  quickNavTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  quickNavSub: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 15,
  },
  soundboxBanner: {
    backgroundColor: '#064e3b',
    borderBottomWidth: 1,
    borderBottomColor: '#059669',
    paddingHorizontal: 20,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    zIndex: 100,
  },
  soundboxLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 10,
  },
  soundboxIconBadge: {
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: 'rgba(52, 211, 153, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  soundboxTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#34d399',
    marginBottom: 1,
  },
  soundboxSpeech: {
    fontSize: 11,
    color: '#e2e8f0',
    fontStyle: 'italic',
  },
  soundboxActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginLeft: 12,
  },
  soundboxReplayBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#059669',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
  },
  soundboxReplayText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
  },
  soundboxDismissBtn: {
    backgroundColor: 'rgba(15, 23, 42, 0.08)',
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
