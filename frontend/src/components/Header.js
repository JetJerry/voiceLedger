import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  TextInput,
  useWindowDimensions,
  ScrollView,
} from 'react-native';
import {
  Mic,
  Settings,
  ShieldCheck,
  Receipt,
  Package,
  LogOut,
  Store,
  Zap,
} from 'lucide-react-native';
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
          <View style={[styles.logoBadge, isAdmin && styles.logoBadgeAdmin]}>
            <Mic size={20} color="#ffffff" strokeWidth={2.5} />
          </View>
          <View style={styles.titleWrap}>
            <View style={styles.brandTitleRow}>
              <Text style={styles.appName}>VoiceLedger</Text>
              {isAdmin ? (
                <View style={styles.adminBadge}>
                  <ShieldCheck size={12} color="#a78bfa" style={{ marginRight: 4 }} />
                  <Text style={styles.adminBadgeText}>Platform Admin</Text>
                </View>
              ) : currentUser?.name ? (
                <View style={styles.storeBadge}>
                  <Store size={12} color={colors.primary} style={{ marginRight: 4 }} />
                  <Text style={styles.storeBadgeText} numberOfLines={1}>
                    {currentUser.name}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text style={styles.appSubtitle} numberOfLines={1}>
              {isAdmin
                ? 'Multi-Store Supervision & Live Settlement Hub'
                : 'Intelligent Voice Settlement & Revenue Engine'}
            </Text>
          </View>
        </View>

        {/* Navigation Tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.navTabsScroll}>
          <View style={styles.navTabs}>
            {isAdmin ? (
              <TouchableOpacity
                style={[styles.navTab, currentView === 'admin' && styles.navTabAdminActive]}
                onPress={() => onSelectView && onSelectView('admin')}
                activeOpacity={0.8}
              >
                <Zap size={14} color={currentView === 'admin' ? '#ffffff' : colors.textSecondary} style={{ marginRight: 6 }} />
                <Text style={[styles.navTabText, currentView === 'admin' && styles.navTabTextActive]}>
                  Multi-Vendor Admin Hub
                </Text>
              </TouchableOpacity>
            ) : (
              <>
                <TouchableOpacity
                  style={[styles.navTab, currentView === 'terminal' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('terminal')}
                  activeOpacity={0.8}
                >
                  <Mic size={14} color={currentView === 'terminal' ? '#ffffff' : colors.textSecondary} style={{ marginRight: 6 }} />
                  <Text style={[styles.navTabText, currentView === 'terminal' && styles.navTabTextActive]}>
                    Voice Terminal
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.navTab, currentView === 'sales' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('sales')}
                  activeOpacity={0.8}
                >
                  <Receipt size={14} color={currentView === 'sales' ? '#ffffff' : colors.textSecondary} style={{ marginRight: 6 }} />
                  <Text style={[styles.navTabText, currentView === 'sales' && styles.navTabTextActive]}>
                    Sales & Ledger
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.navTab, currentView === 'catalog' && styles.navTabActive]}
                  onPress={() => onSelectView && onSelectView('catalog')}
                  activeOpacity={0.8}
                >
                  <Package size={14} color={currentView === 'catalog' ? '#ffffff' : colors.textSecondary} style={{ marginRight: 6 }} />
                  <Text style={[styles.navTabText, currentView === 'catalog' && styles.navTabTextActive]}>
                    Product Catalog
                  </Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </ScrollView>

        {/* Right Actions: Test Badge, Settings, Logout */}
        <View style={styles.badgesContainer}>
          {!isMobile && (
            <View style={styles.pillRzp}>
              <View style={styles.dotLive} />
              <Text style={styles.pillText}>Razorpay Test Mode</Text>
            </View>
          )}

          <TouchableOpacity
            style={styles.iconButton}
            onPress={() => {
              setApiUrlInput(getApiBase());
              setSettingsModalVisible(true);
            }}
            activeOpacity={0.7}
            accessibilityLabel="API Settings"
          >
            <Settings size={16} color={colors.textSecondary} />
          </TouchableOpacity>

          {onLogout && (
            <TouchableOpacity
              style={styles.logoutBtn}
              onPress={onLogout}
              activeOpacity={0.8}
              accessibilityLabel="Sign out"
            >
              <LogOut size={14} color={colors.accentRose} style={{ marginRight: 5 }} />
              <Text style={styles.logoutBtnText}>Logout</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Settings Modal */}
      <Modal
        visible={settingsModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setSettingsModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeaderRow}>
              <Settings size={18} color={colors.primary} style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Backend API Configuration</Text>
            </View>
            <Text style={styles.modalDesc}>
              Specify your server endpoint URL (e.g. Modal cloud deployment or local development server):
            </Text>

            <TextInput
              style={styles.ipInput}
              value={apiUrlInput}
              onChangeText={setApiUrlInput}
              placeholder="https://your-workspace.modal.run/api"
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
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
    backgroundColor: '#F8FAFC',
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
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  logoBadgeAdmin: {
    backgroundColor: '#7c3aed',
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
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  storeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderColor: 'rgba(99, 102, 241, 0.25)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  storeBadgeText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '600',
  },
  adminBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(124, 58, 237, 0.15)',
    borderColor: 'rgba(124, 58, 237, 0.3)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  adminBadgeText: {
    color: colors.accentViolet,
    fontSize: 11,
    fontWeight: '700',
  },
  appSubtitle: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  navTabsScroll: {
    marginHorizontal: 12,
  },
  navTabs: {
    flexDirection: 'row',
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderRadius: 10,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  navTab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 8,
  },
  navTabActive: {
    backgroundColor: colors.primary,
  },
  navTabAdminActive: {
    backgroundColor: '#7c3aed',
  },
  navTabText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  navTabTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  badgesContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pillRzp: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.25)',
  },
  dotLive: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10b981',
    marginRight: 6,
  },
  pillText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#34d399',
  },
  iconButton: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(244, 63, 94, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.25)',
  },
  logoutBtnText: {
    color: colors.accentRose,
    fontSize: 12,
    fontWeight: '600',
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
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
  },
  modalHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  modalDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: 16,
  },
  ipInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 13,
    marginBottom: 20,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  btn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnCancel: {
    backgroundColor: 'rgba(15, 23, 42, 0.05)',
  },
  btnCancelText: {
    color: colors.textSecondary,
    fontWeight: '600',
    fontSize: 12,
  },
  btnSave: {
    backgroundColor: colors.primary,
  },
  btnSaveText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 12,
  },
});
