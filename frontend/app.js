import React, { useState, useEffect, useCallback } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  StatusBar,
  RefreshControl,
  useWindowDimensions,
  Platform,
} from 'react-native';
import { colors } from './src/theme/colors';
import { apiService } from './src/services/apiService';
import Header from './src/components/Header';
import VoiceAssistantCard from './src/components/VoiceAssistantCard';
import MetricsGrid from './src/components/MetricsGrid';
import SalesLedger from './src/components/SalesLedger';
import PaymentSimModal from './src/components/PaymentSimModal';

export default function App() {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [summaryData, setSummaryData] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeSimSale, setActiveSimSale] = useState(null);
  const [isSimSubmitting, setIsSimSubmitting] = useState(false);

  // Fetch Dashboard summary & sales
  const loadDashboard = useCallback(async () => {
    try {
      const data = await apiService.getDashboardSummary();
      setSummaryData(data);
    } catch (e) {
      console.warn('Dashboard fetch notice:', e.message);
    }
  }, []);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await loadDashboard();
    setIsRefreshing(false);
  };

  useEffect(() => {
    loadDashboard();

    // Auto-refresh every 5 seconds for live webhook arrival
    const interval = setInterval(loadDashboard, 5000);
    return () => clearInterval(interval);
  }, [loadDashboard]);

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

  return (
    <SafeAreaView style={styles.rootContainer}>
      <StatusBar barStyle="light-content" backgroundColor={colors.bgDark} />

      {/* Background Ambient Glows */}
      <View style={[styles.ambientGlow, styles.glow1]} pointerEvents="none" />
      <View style={[styles.ambientGlow, styles.glow2]} pointerEvents="none" />

      {/* Fixed App Header */}
      <Header onRefresh={loadDashboard} />

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
        {/* 1. Hero Voice Assistant Card */}
        <VoiceAssistantCard onActionComplete={loadDashboard} />

        {/* 2. KPIs & Metrics Grid */}
        <MetricsGrid summary={summaryData} />

        {/* 3. Real-Time Product Sales & Payment Ledger */}
        <SalesLedger
          sales={summaryData?.recent_sales || []}
          onRefresh={handleManualRefresh}
          onSimulatePayment={handleOpenSimulate}
          isRefreshing={isRefreshing}
        />

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            VoiceLedger — Universal React Native (Web & Mobile) Payment Collection Agent
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
});
