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
import { colors } from './src/theme/colors';
import { apiService } from './src/services/apiService';
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
  };

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await loadDashboard();
    setIsRefreshing(false);
  };

  useEffect(() => {
    if (!currentUser) return;
    loadDashboard();

    // Auto-refresh every 5 seconds for live webhook arrival
    const interval = setInterval(loadDashboard, 5000);
    return () => clearInterval(interval);
  }, [currentUser, loadDashboard]);

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
      <StatusBar barStyle="light-content" backgroundColor={colors.bgDark} />

      {/* Background Ambient Glows */}
      <View style={[styles.ambientGlow, styles.glow1]} pointerEvents="none" />
      <View style={[styles.ambientGlow, styles.glow2]} pointerEvents="none" />

      {/* Fixed App Header with Nav Tabs & Logout */}
      <Header
        onRefresh={loadDashboard}
        currentView={currentView}
        onSelectView={setCurrentView}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

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
        {/* PAGE 1: 🎙️ Simple, Clean Voice Dashboard */}
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
                  <Text style={styles.quickNavIcon}>🧾</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.quickNavTitle}>Sales & Payment Ledger</Text>
                  <Text style={styles.quickNavSub}>
                    View {summaryData?.total_transactions || 0} recorded orders, check payment arrival, and verify Razorpay links.
                  </Text>
                </View>
                <Text style={styles.quickNavArrow}>→</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.quickNavCard}
                onPress={() => setCurrentView('catalog')}
                activeOpacity={0.8}
              >
                <View style={[styles.quickNavIconWrap, { backgroundColor: 'rgba(6, 182, 212, 0.15)' }]}>
                  <Text style={styles.quickNavIcon}>📦</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.quickNavTitle}>Store Menu & Items</Text>
                  <Text style={styles.quickNavSub}>
                    Add items with dynamic attributes (Fruits, Medicines, Kirana, Cafe, Clothes, Hardware).
                  </Text>
                </View>
                <Text style={styles.quickNavArrow}>→</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* PAGE 2: 🧾 Dedicated Sales & Payments Ledger */}
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

        {/* PAGE 3: 📦 Dedicated Store Menu & Catalog Manager */}
        {currentView === 'catalog' && (
          <View style={styles.pageWrap}>
            <CatalogManager onCatalogUpdated={loadDashboard} />
          </View>
        )}

        {/* PAGE 4: ⚡ Dedicated Admin Multi-Merchant Hub */}
        {currentView === 'admin' && (
          <View style={styles.pageWrap}>
            <AdminDashboard
              onSwitchToTerminal={(merchant) => {
                setActiveStore(merchant);
                setCurrentView('terminal');
                loadDashboard();
              }}
              onRefreshApp={loadDashboard}
            />
          </View>
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            VoiceLedger — Universal React Native Multi-Domain Store Assistant
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
    backgroundColor: colors.bgDark,
    position: 'relative',
  },
  ambientGlow: {
    position: 'absolute',
    borderRadius: 999,
  },
  glow1: {
    top: -50,
    left: '15%',
    width: 380,
    height: 380,
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
  },
  glow2: {
    bottom: 50,
    right: -50,
    width: 420,
    height: 420,
    backgroundColor: 'rgba(139, 92, 246, 0.06)',
  },
  scrollContainer: {
    flex: 1,
  },
  scrollContent: {
    paddingVertical: 24,
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
    paddingHorizontal: 16,
  },
  footer: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },

  // Restructured Page Containers & Quick Nav
  pageWrap: {
    width: '100%',
  },
  quickNavRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 24,
  },
  quickNavRowMobile: {
    flexDirection: 'column',
    gap: 12,
  },
  quickNavCard: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 16,
  },
  quickNavIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  quickNavIcon: {
    fontSize: 22,
  },
  quickNavTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  quickNavSub: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  quickNavArrow: {
    fontSize: 20,
    color: colors.primary,
    fontWeight: '800',
    marginLeft: 10,
  },
});
