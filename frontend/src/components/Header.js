import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Modal, TextInput, useWindowDimensions, ScrollView } from 'react-native';
import { Mic, Settings, Wifi, CheckCircle2, Sparkles } from 'lucide-react-native';
import { colors } from '../theme/colors';
import { getApiBase, setCustomApiBase } from '../config/api';

export default function Header({
  onRefresh,
  currentView = 'terminal',
  onSelectView,
  currentUser,
  onLogout,
}) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [apiUrlInput, setApiUrlInput] = useState(getApiBase());

  const handleSaveApiUrl = () => {
    setCustomApiBase(apiUrlInput);
    setSettingsModalVisible(false);
    if (onRefresh) onRefresh();
  };

  const isAdmin = currentUser?.role === 'admin';

  return (
    <View style={styles.headerContainer}>
      <View style={styles.topRow}>
        {/* Brand Group */}
        <View style={styles.brandGroup}>
          <View style={[styles.logoBadge, isAdmin && { backgroundColor: '#8b5cf6' }]}>
            <Mic size={22} color="#ffffff" strokeWidth={2.5} />
          </View>
          <View style={styles.titleWrap}>
            <View style={styles.brandTitleRow}>
              <Text style={styles.appName}>VoiceLedger</Text>
              {isAdmin ? (
                <View style={[styles.storeBadge, { backgroundColor: 'rgba(139, 92, 246, 0.2)', borderColor: '#8b5cf6' }]}>
                  <Text style={[styles.storeBadgeText, { color: '#c4b5fd' }]}>
                    ⚡ Platform Super Admin
                  </Text>
                </View>
              ) : currentUser?.name ? (
                <View style={styles.storeBadge}>
                  <Text style={styles.storeBadgeText} numberOfLines={1}>
                    🏪 {currentUser.name}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text style={styles.appSubtitle} numberOfLines={1}>
              {isAdmin
                ? 'Multi-Store Supervision & Live Payment Reconciliation'
                : 'Voice-First Sales & Payment Arrival Verification'}
            </Text>
          </View>
        </View>

        {/* Role-Specific Navigation Tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.navTabsScroll}>
          <View style={styles.navTabs}>
            {isAdmin ? (
              /* Admin Navigation Tab */
              <TouchableOpacity
                style={[styles.navTab, currentView === 'admin' && styles.navTabAdminActive]}
                onPress={() => onSelectView && onSelectView('admin')}
                activeOpacity={0.8}
              >
                <Text style={[styles.navTabText, currentView === 'admin' && styles.navTabTextActive]}>
                  ⚡ Multi-Vendor Admin Hub
                </Text>
              </TouchableOpacity>
            ) : (
              /* Shopkeeper Navigation Tabs (Strictly no admin tabs in merchant terminal) */
              <>
                <TouchableOpacity
                  style={[styles.navTab, currentView === 'terminal' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('terminal')}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.navTabText, currentView === 'terminal' && styles.navTabTextActive]}>
                    🎙️ Voice Terminal
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.navTab, currentView === 'sales' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('sales')}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.navTabText, currentView === 'sales' && styles.navTabTextActive]}>
                    🧾 Sales & Payments
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.navTab, currentView === 'catalog' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('catalog')}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.navTabText, currentView === 'catalog' && styles.navTabTextActive]}>
                    📦 Menu & Items
                  </Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </ScrollView>

        {/* Status Badges, Settings & Logout */}
        <View style={styles.badgesContainer}>
          {!isMobile && (
            <View style={[styles.pill, styles.pillRzp]}>
              <View style={styles.dotLive} />
              <Text style={styles.pillText}>Razorpay Test</Text>
            </View>
          )}

          <TouchableOpacity
            style={styles.settingsBtn}
            onPress={() => {
              setApiUrlInput(getApiBase());
              setSettingsModalVisible(true);
            }}
            activeOpacity={0.7}
          >
            <Settings size={18} color={colors.textSecondary} />
          </TouchableOpacity>

          {/* Logout Button */}
          {onLogout && (
            <TouchableOpacity
              style={styles.logoutBtn}
              onPress={onLogout}
              activeOpacity={0.8}
            >
              <Text style={styles.logoutBtnText}>🚪 Logout</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Settings Modal (For setting backend IP on physical phones) */}
      <Modal
        visible={settingsModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setSettingsModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>⚙️ Backend API Configuration</Text>
            <Text style={styles.modalDesc}>
              When running on a physical smartphone with Expo Go, enter your computer's local Wi-Fi IP address (e.g. http://192.168.1.5:8000/api):
            </Text>

            <TextInput
              style={styles.ipInput}
              value={apiUrlInput}
              onChangeText={setApiUrlInput}
              placeholder="http://192.168.1.X:8000/api"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={[styles.btn, styles.btnCancel]}
                onPress={() => setSettingsModalVisible(false)}
              >
                <Text style={styles.btnCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.btnSave]}
                onPress={handleSaveApiUrl}
              >
                <Text style={styles.btnSaveText}>Save & Reconnect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  headerContainer: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
    backgroundColor: 'rgba(10, 14, 23, 0.85)',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    maxWidth: 1200,
    width: '100%',
    alignSelf: 'center',
  },
  brandGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  logoBadge: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 6,
  },
  titleWrap: {
    flex: 1,
  },
  brandTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  appName: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.5,
  },
  storeBadge: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderColor: 'rgba(99, 102, 241, 0.3)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  storeBadgeText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '700',
  },
  appSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  navTabs: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginHorizontal: 12,
  },
  navTab: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 9,
  },
  navTabActive: {
    backgroundColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
  },
  navTabText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  navTabTextActive: {
    color: '#ffffff',
  },
  badgesContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
  },
  pillRzp: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  pillAi: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderColor: 'rgba(99, 102, 241, 0.3)',
  },
  dotLive: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#10b981',
    marginRight: 6,
  },
  pillText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6ee7b7',
  },
  settingsBtn: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    maxWidth: 480,
    backgroundColor: '#121826',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 8,
  },
  modalDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: 16,
  },
  ipInput: {
    backgroundColor: '#0a0e17',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
    marginBottom: 20,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  btn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnCancel: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  btnCancelText: {
    color: colors.textSecondary,
    fontWeight: '600',
    fontSize: 13,
  },
  btnSave: {
    backgroundColor: colors.primary,
  },
  btnSaveText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 13,
  },
  navTabAdminActive: {
    backgroundColor: '#8b5cf6',
  },
  logoutBtn: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: 'rgba(244, 63, 94, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.3)',
    marginLeft: 6,
  },
  logoutBtnText: {
    color: colors.accentRose,
    fontSize: 12,
    fontWeight: '700',
  },
});
