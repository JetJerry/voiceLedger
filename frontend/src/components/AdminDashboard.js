import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Modal,
  ScrollView,
  useWindowDimensions,
} from 'react-native';
import { colors } from '../theme/colors';
import { apiService } from '../services/apiService';

const BUSINESS_CATEGORIES = [
  'Kirana & Grocery',
  'Cafe & Fast Food',
  'Bakery & Sweets',
  'Stationery & Printing',
  'Dairy & Fresh Milk',
  'Apparel & Clothing',
  'Hardware & Tools',
  'General Store',
];

export default function AdminDashboard({ onSwitchToTerminal, onRefreshApp }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [metrics, setMetrics] = useState(null);
  const [merchants, setMerchants] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  // Onboard Modal State
  const [modalVisible, setModalVisible] = useState(false);
  const [newStoreName, setNewStoreName] = useState('');
  const [newBusinessType, setNewBusinessType] = useState('Kirana & Grocery');
  const [newPhone, setNewPhone] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const loadAdminData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [mStats, mList] = await Promise.all([
        apiService.getAdminMetrics().catch(() => null),
        apiService.getAdminMerchants(searchQuery).catch(() => []),
      ]);
      setMetrics(mStats);
      setMerchants(mList);
    } catch (e) {
      console.warn('Admin fetch error:', e.message);
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  const handleCreateMerchant = async () => {
    if (!newStoreName.trim()) {
      setFormError('Store name is required');
      return;
    }
    setFormError('');
    setIsSubmitting(true);
    try {
      await apiService.createMerchant({
        name: newStoreName.trim(),
        business_type: newBusinessType,
        phone: newPhone.trim() || undefined,
      });
      setModalVisible(false);
      setNewStoreName('');
      setNewPhone('');
      await loadAdminData();
      if (onRefreshApp) onRefreshApp();
    } catch (err) {
      setFormError(err.message || 'Failed to create merchant');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetActiveStore = async (merchant) => {
    try {
      await apiService.setActiveMerchant(merchant.id);
      await loadAdminData();
      if (onSwitchToTerminal) onSwitchToTerminal(merchant);
      if (onRefreshApp) onRefreshApp();
    } catch (err) {
      alert(`Error setting active store: ${err.message}`);
    }
  };

  const handleToggleStatus = async (merchant) => {
    try {
      await apiService.updateMerchant(merchant.id, { is_active: !merchant.is_active });
      await loadAdminData();
      if (onRefreshApp) onRefreshApp();
    } catch (err) {
      alert(`Error toggling status: ${err.message}`);
    }
  };

  const formatCurrency = (val) => {
    const num = Number(val) || 0;
    return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const filteredMerchants = merchants.filter((m) => {
    if (selectedCategory !== 'ALL' && m.business_type !== selectedCategory) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (m.name || '').toLowerCase().includes(q);
      const matchType = (m.business_type || '').toLowerCase().includes(q);
      const matchPhone = (m.phone || '').includes(q);
      return matchName || matchType || matchPhone;
    }
    return true;
  });

  return (
    <View style={styles.container}>
      {/* 1. Header & Actions Bar */}
      <View style={[styles.titleRow, isMobile && styles.titleRowMobile]}>
        <View>
          <View style={styles.badgeHub}>
            <Text style={styles.badgeHubText}>⚡ Multi-Store Management</Text>
          </View>
          <Text style={styles.mainTitle}>Platform Admin Hub</Text>
          <Text style={styles.subTitle}>
            Oversee all registered shopkeepers, track total platform revenue, and switch active store contexts.
          </Text>
        </View>

        <TouchableOpacity
          style={styles.onboardBtn}
          onPress={() => {
            setFormError('');
            setModalVisible(true);
          }}
          activeOpacity={0.8}
        >
          <Text style={styles.onboardBtnIcon}>➕</Text>
          <Text style={styles.onboardBtnText}>Onboard Shopkeeper</Text>
        </TouchableOpacity>
      </View>

      {/* 2. Platform KPI Metrics Grid */}
      <View style={[styles.metricsGrid, isMobile && styles.metricsGridMobile]}>
        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <Text style={styles.kpiEmoji}>🌐</Text>
            <Text style={styles.kpiLabel}>Total Platform GMV</Text>
          </View>
          <Text style={styles.kpiValue}>{formatCurrency(metrics?.total_gmv)}</Text>
          <Text style={styles.kpiSub}>Across all registered merchants</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <Text style={styles.kpiEmoji}>💳</Text>
            <Text style={styles.kpiLabel}>Total Collected</Text>
          </View>
          <Text style={[styles.kpiValue, { color: colors.accentEmerald }]}>
            {formatCurrency(metrics?.total_collected)}
          </Text>
          <Text style={styles.kpiSub}>{metrics?.collection_rate_percent || 100}% collection rate</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <Text style={styles.kpiEmoji}>⏳</Text>
            <Text style={styles.kpiLabel}>Total Outstanding</Text>
          </View>
          <Text style={[styles.kpiValue, { color: colors.accentRose }]}>
            {formatCurrency(metrics?.total_outstanding)}
          </Text>
          <Text style={styles.kpiSub}>Unpaid receivables across platform</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <Text style={styles.kpiEmoji}>🏪</Text>
            <Text style={styles.kpiLabel}>Registered Stores</Text>
          </View>
          <View style={styles.vendorCountRow}>
            <Text style={styles.kpiValue}>{metrics?.total_merchants || 0}</Text>
            <View style={styles.activePill}>
              <Text style={styles.activePillText}>{metrics?.active_merchants || 0} Active</Text>
            </View>
          </View>
          <Text style={styles.kpiSub}>{metrics?.total_transactions || 0} total sales processed</Text>
        </View>
      </View>

      {/* 3. Search & Filter Bar */}
      <View style={styles.searchBarContainer}>
        <View style={styles.searchInputWrapper}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            style={styles.searchInput}
            placeholder="Search stores by name, category, or phone..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearSearchBtn}>
              <Text style={styles.clearSearchText}>✕</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
          <TouchableOpacity
            style={[styles.filterChip, selectedCategory === 'ALL' && styles.filterChipActive]}
            onPress={() => setSelectedCategory('ALL')}
          >
            <Text style={[styles.filterChipText, selectedCategory === 'ALL' && styles.filterChipTextActive]}>
              All Categories ({merchants.length})
            </Text>
          </TouchableOpacity>
          {BUSINESS_CATEGORIES.map((cat) => {
            const count = merchants.filter((m) => m.business_type === cat).length;
            if (count === 0) return null;
            return (
              <TouchableOpacity
                key={cat}
                style={[styles.filterChip, selectedCategory === cat && styles.filterChipActive]}
                onPress={() => setSelectedCategory(cat)}
              >
                <Text style={[styles.filterChipText, selectedCategory === cat && styles.filterChipTextActive]}>
                  {cat} ({count})
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* 4. Merchants Cards Grid */}
      {isLoading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading shopkeepers and platform metrics...</Text>
        </View>
      ) : filteredMerchants.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyEmoji}>🏪</Text>
          <Text style={styles.emptyTitle}>No shopkeepers found</Text>
          <Text style={styles.emptySub}>
            {searchQuery ? 'Try clearing your search filter.' : 'Click "Onboard Shopkeeper" to register your first store.'}
          </Text>
        </View>
      ) : (
        <View style={[styles.merchantGrid, isMobile && styles.merchantGridMobile]}>
          {filteredMerchants.map((m) => {
            const isCurrent = m.is_current_active;
            const collectedPercent =
              m.total_sales_volume > 0 ? Math.round((m.total_collected / m.total_sales_volume) * 100) : 100;

            return (
              <View key={m.id} style={[styles.merchantCard, isCurrent && styles.merchantCardCurrent]}>
                {/* Store Header */}
                <View style={styles.mCardTop}>
                  <View style={styles.mStoreInfo}>
                    <View style={[styles.mAvatar, isCurrent && styles.mAvatarCurrent]}>
                      <Text style={styles.mAvatarEmoji}>
                        {m.business_type?.includes('Cafe') || m.business_type?.includes('Food')
                          ? '☕'
                          : m.business_type?.includes('Bakery') || m.business_type?.includes('Sweet')
                          ? '🧁'
                          : m.business_type?.includes('Stationery')
                          ? '📚'
                          : m.business_type?.includes('Dairy')
                          ? '🥛'
                          : '🛒'}
                      </Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <View style={styles.nameRow}>
                        <Text style={styles.mName} numberOfLines={1}>
                          {m.name}
                        </Text>
                      </View>
                      <View style={styles.tagRow}>
                        <View style={styles.catBadge}>
                          <Text style={styles.catBadgeText}>{m.business_type || 'Retail'}</Text>
                        </View>
                        {m.phone ? <Text style={styles.phoneText}>📞 {m.phone}</Text> : null}
                      </View>
                    </View>
                  </View>

                  <View style={styles.statusPillWrapper}>
                    {isCurrent ? (
                      <View style={styles.currentActivePill}>
                        <Text style={styles.currentActiveText}>🟢 Live Terminal</Text>
                      </View>
                    ) : (
                      <TouchableOpacity
                        style={[styles.statusToggle, !m.is_active && styles.statusToggleInactive]}
                        onPress={() => handleToggleStatus(m)}
                      >
                        <Text style={[styles.statusToggleText, !m.is_active && styles.statusToggleTextInactive]}>
                          {m.is_active ? 'Active' : 'Inactive'}
                        </Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>

                {/* Financial Summary */}
                <View style={styles.mStatsGrid}>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Catalog Items</Text>
                    <Text style={styles.mStatValue}>{m.products_count || 0}</Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Sales Count</Text>
                    <Text style={styles.mStatValue}>{m.total_sales_count || 0}</Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Gross Sales</Text>
                    <Text style={[styles.mStatValue, { color: colors.textPrimary }]}>
                      {formatCurrency(m.total_sales_volume)}
                    </Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Collected</Text>
                    <Text style={[styles.mStatValue, { color: colors.accentEmerald }]}>
                      {formatCurrency(m.total_collected)}
                    </Text>
                  </View>
                </View>

                {/* Collection Progress Bar */}
                <View style={styles.progressContainer}>
                  <View style={styles.progressLabels}>
                    <Text style={styles.progressLabelText}>Collection Rate</Text>
                    <Text style={styles.progressPercentText}>{collectedPercent}%</Text>
                  </View>
                  <View style={styles.progressBarBg}>
                    <View style={[styles.progressBarFill, { width: `${Math.min(collectedPercent, 100)}%` }]} />
                  </View>
                </View>

                {/* Actions Footer */}
                <View style={styles.mCardActions}>
                  {isCurrent ? (
                    <TouchableOpacity
                      style={styles.openTerminalBtn}
                      onPress={() => onSwitchToTerminal && onSwitchToTerminal(m)}
                    >
                      <Text style={styles.openTerminalBtnText}>🎙️ Open Store Terminal</Text>
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity style={styles.switchStoreBtn} onPress={() => handleSetActiveStore(m)}>
                      <Text style={styles.switchStoreBtnText}>⚡ Switch Active Store</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            );
          })}
        </View>
      )}

      {/* 5. Onboard Shopkeeper Modal */}
      <Modal visible={modalVisible} transparent animationType="fade" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, isMobile && styles.modalCardMobile]}>
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>Onboard New Shopkeeper</Text>
                <Text style={styles.modalSub}>Register a new store / vendor context on VoiceLedger</Text>
              </View>
              <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setModalVisible(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            {formError ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>⚠️ {formError}</Text>
              </View>
            ) : null}

            {/* Store Name Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Store / Business Name *</Text>
              <TextInput
                style={styles.formInput}
                placeholder="e.g. Royal Men's Apparel & Shoes"
                placeholderTextColor={colors.textMuted}
                value={newStoreName}
                onChangeText={setNewStoreName}
              />
            </View>

            {/* Business Category Selector */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Business Category</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.catSelectorScroll}>
                {BUSINESS_CATEGORIES.map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.catSelectChip, newBusinessType === cat && styles.catSelectChipActive]}
                    onPress={() => setNewBusinessType(cat)}
                  >
                    <Text
                      style={[styles.catSelectChipText, newBusinessType === cat && styles.catSelectChipTextActive]}
                    >
                      {cat}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>

            {/* Phone Number Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Contact Phone (Optional)</Text>
              <TextInput
                style={styles.formInput}
                placeholder="e.g. +91 98765 43210"
                placeholderTextColor={colors.textMuted}
                value={newPhone}
                onChangeText={setNewPhone}
                keyboardType="phone-pad"
              />
            </View>

            {/* Actions */}
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setModalVisible(false)}
                disabled={isSubmitting}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleCreateMerchant}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>Register Store</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    marginBottom: 32,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 24,
    gap: 16,
    flexWrap: 'wrap',
  },
  titleRowMobile: {
    flexDirection: 'column',
    alignItems: 'stretch',
  },
  badgeHub: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.3)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  badgeHubText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  mainTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: colors.textPrimary,
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  subTitle: {
    fontSize: 14,
    color: colors.textSecondary,
    maxWidth: 650,
    lineHeight: 20,
  },
  onboardBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
  },
  onboardBtnIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  onboardBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 14,
  },

  // KPI Grid
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
    marginBottom: 24,
  },
  metricsGridMobile: {
    flexDirection: 'column',
    gap: 12,
  },
  kpiCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 18,
  },
  kpiQuarter: {
    flex: 1,
    minWidth: 220,
  },
  kpiFull: {
    width: '100%',
  },
  kpiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  kpiEmoji: {
    fontSize: 18,
    marginRight: 8,
  },
  kpiLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  kpiValue: {
    fontSize: 24,
    fontWeight: '900',
    color: colors.textPrimary,
    letterSpacing: -0.5,
  },
  kpiSub: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 4,
  },
  vendorCountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  activePill: {
    backgroundColor: colors.badgePaidBg,
    borderColor: colors.badgePaidBorder,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  activePillText: {
    color: colors.badgePaidText,
    fontSize: 11,
    fontWeight: '700',
  },

  // Search & Filter Bar
  searchBarContainer: {
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 16,
    marginBottom: 24,
  },
  searchInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    marginBottom: 12,
  },
  searchIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    height: 44,
    color: colors.textPrimary,
    fontSize: 14,
  },
  clearSearchBtn: {
    padding: 6,
  },
  clearSearchText: {
    color: colors.textMuted,
    fontSize: 14,
  },
  filterScroll: {
    flexDirection: 'row',
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  filterChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  filterChipText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  filterChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },

  // Merchant Cards Grid
  merchantGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  merchantGridMobile: {
    flexDirection: 'column',
  },
  merchantCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 20,
    flex: 1,
    minWidth: 320,
    maxWidth: '100%',
  },
  merchantCardCurrent: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(28, 36, 60, 0.9)',
  },
  mCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
    gap: 12,
  },
  mStoreInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  mAvatar: {
    width: 46,
    height: 46,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  mAvatarCurrent: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderColor: colors.primary,
  },
  mAvatarEmoji: {
    fontSize: 22,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mName: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  tagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
    flexWrap: 'wrap',
  },
  catBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  catBadgeText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  phoneText: {
    color: colors.textMuted,
    fontSize: 11,
  },
  statusPillWrapper: {
    alignItems: 'flex-end',
  },
  currentActivePill: {
    backgroundColor: colors.badgePaidBg,
    borderColor: colors.badgePaidBorder,
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  currentActiveText: {
    color: colors.badgePaidText,
    fontSize: 11,
    fontWeight: '800',
  },
  statusToggle: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  statusToggleInactive: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderColor: colors.borderColor,
  },
  statusToggleText: {
    color: colors.badgePaidText,
    fontSize: 11,
    fontWeight: '700',
  },
  statusToggleTextInactive: {
    color: colors.textMuted,
  },

  // Stats Grid inside Card
  mStatsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
  },
  mStatItem: {
    alignItems: 'center',
  },
  mStatLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginBottom: 2,
    fontWeight: '600',
  },
  mStatValue: {
    fontSize: 14,
    fontWeight: '800',
    color: colors.textPrimary,
  },

  // Progress Bar
  progressContainer: {
    marginBottom: 16,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  progressLabelText: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
  },
  progressPercentText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '700',
  },
  progressBarBg: {
    height: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: 99,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.accentEmerald,
    borderRadius: 99,
  },

  // Actions
  mCardActions: {
    marginTop: 4,
  },
  switchStoreBtn: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderColor: 'rgba(99, 102, 241, 0.3)',
    borderWidth: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  switchStoreBtnText: {
    color: colors.primary,
    fontWeight: '700',
    fontSize: 13,
  },
  openTerminalBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  openTerminalBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 13,
  },

  // Loading & Empty States
  loadingBox: {
    padding: 60,
    alignItems: 'center',
  },
  loadingText: {
    color: colors.textSecondary,
    marginTop: 12,
    fontSize: 14,
  },
  emptyBox: {
    padding: 50,
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  emptyEmoji: {
    fontSize: 40,
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySub: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    backgroundColor: '#121826',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
    width: '100%',
    maxWidth: 520,
  },
  modalCardMobile: {
    maxWidth: '100%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  modalSub: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 2,
  },
  modalCloseBtn: {
    padding: 4,
  },
  modalCloseText: {
    color: colors.textMuted,
    fontSize: 18,
  },
  errorBox: {
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    borderColor: 'rgba(244, 63, 94, 0.3)',
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    marginBottom: 16,
  },
  errorText: {
    color: colors.accentRose,
    fontSize: 13,
    fontWeight: '600',
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  formInput: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 10,
    paddingHorizontal: 14,
    height: 46,
    color: colors.textPrimary,
    fontSize: 14,
  },
  catSelectorScroll: {
    flexDirection: 'row',
  },
  catSelectChip: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderColor: colors.borderColor,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
  },
  catSelectChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  catSelectChipText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  catSelectChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 10,
  },
  cancelBtn: {
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  cancelBtnText: {
    color: colors.textSecondary,
    fontWeight: '700',
    fontSize: 14,
  },
  submitBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 22,
    borderRadius: 10,
    minWidth: 120,
    alignItems: 'center',
  },
  submitBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 14,
  },
});
