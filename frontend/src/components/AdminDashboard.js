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
import {
  ShieldCheck,
  Plus,
  Globe,
  CreditCard,
  Clock,
  Store,
  Search,
  Phone,
  Radio,
  CheckCircle2,
  TrendingUp,
  X,
  AlertCircle,
} from 'lucide-react-native';
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
          <Text style={styles.mainTitle}>Platform Admin Supervision Hub</Text>
          <Text style={styles.subTitle}>
            Multi-store oversight, settlement volumes, merchant context switching, and platform analytics.
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
          <Plus size={15} color="#ffffff" style={{ marginRight: 6 }} />
          <Text style={styles.onboardBtnText}>Onboard Merchant</Text>
        </TouchableOpacity>
      </View>

      {/* 2. Platform KPI Metrics Grid */}
      <View style={[styles.metricsGrid, isMobile && styles.metricsGridMobile]}>
        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <View style={[styles.kpiIconWrap, { backgroundColor: 'rgba(99, 102, 241, 0.12)' }]}>
              <Globe size={15} color={colors.primary} />
            </View>
            <Text style={styles.kpiLabel}>Total Platform GMV</Text>
          </View>
          <Text style={styles.kpiValue}>{formatCurrency(metrics?.total_gmv)}</Text>
          <Text style={styles.kpiSub}>Consolidated across all stores</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <View style={[styles.kpiIconWrap, { backgroundColor: 'rgba(16, 185, 129, 0.12)' }]}>
              <CreditCard size={15} color={colors.accentEmerald} />
            </View>
            <Text style={styles.kpiLabel}>Settled Volume</Text>
          </View>
          <Text style={[styles.kpiValue, { color: colors.accentEmerald }]}>
            {formatCurrency(metrics?.total_collected)}
          </Text>
          <Text style={styles.kpiSub}>{metrics?.collection_rate_percent || 100}% settlement efficiency</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <View style={[styles.kpiIconWrap, { backgroundColor: 'rgba(244, 63, 94, 0.12)' }]}>
              <Clock size={15} color={colors.accentRose} />
            </View>
            <Text style={styles.kpiLabel}>Outstanding Balance</Text>
          </View>
          <Text style={[styles.kpiValue, { color: colors.accentRose }]}>
            {formatCurrency(metrics?.total_outstanding)}
          </Text>
          <Text style={styles.kpiSub}>Unsettled merchant balances</Text>
        </View>

        <View style={[styles.kpiCard, isMobile ? styles.kpiFull : styles.kpiQuarter]}>
          <View style={styles.kpiHeader}>
            <View style={[styles.kpiIconWrap, { backgroundColor: 'rgba(255, 255, 255, 0.05)' }]}>
              <Store size={15} color={colors.textSecondary} />
            </View>
            <Text style={styles.kpiLabel}>Registered Stores</Text>
          </View>
          <View style={styles.vendorCountRow}>
            <Text style={styles.kpiValue}>{metrics?.total_merchants || 0}</Text>
            <View style={styles.activePill}>
              <Text style={styles.activePillText}>{metrics?.active_merchants || 0} Active</Text>
            </View>
          </View>
          <Text style={styles.kpiSub}>{metrics?.total_transactions || 0} total transactions processed</Text>
        </View>
      </View>

      {/* 3. Search & Filter Bar */}
      <View style={styles.searchBarContainer}>
        <View style={styles.searchInputWrapper}>
          <Search size={15} color={colors.textMuted} style={{ marginRight: 8 }} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search stores by name, category, or phone..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearSearchBtn}>
              <Text style={styles.clearSearchText}>Clear</Text>
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
          <Text style={styles.loadingText}>Loading merchant accounts...</Text>
        </View>
      ) : filteredMerchants.length === 0 ? (
        <View style={styles.emptyBox}>
          <Store size={36} color={colors.textMuted} style={{ marginBottom: 8 }} />
          <Text style={styles.emptyTitle}>No merchant accounts found</Text>
          <Text style={styles.emptySub}>
            {searchQuery ? 'Try adjusting your search criteria.' : 'Click "Onboard Merchant" to register your first store.'}
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
                      <Store size={18} color={isCurrent ? colors.primary : colors.textSecondary} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.mName} numberOfLines={1}>
                        {m.name}
                      </Text>
                      <View style={styles.tagRow}>
                        <View style={styles.catBadge}>
                          <Text style={styles.catBadgeText}>{m.business_type || 'Retail'}</Text>
                        </View>
                        {m.phone ? (
                          <View style={styles.phoneRow}>
                            <Phone size={11} color={colors.textMuted} style={{ marginRight: 4 }} />
                            <Text style={styles.phoneText}>{m.phone}</Text>
                          </View>
                        ) : null}
                      </View>
                    </View>
                  </View>

                  <View style={styles.statusPillWrapper}>
                    {isCurrent ? (
                      <View style={styles.currentActivePill}>
                        <Radio size={11} color="#34d399" style={{ marginRight: 4 }} />
                        <Text style={styles.currentActiveText}>Active Context</Text>
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
                    <Text style={styles.mStatLabel}>Items</Text>
                    <Text style={styles.mStatValue}>{m.products_count || 0}</Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Orders</Text>
                    <Text style={styles.mStatValue}>{m.total_sales_count || 0}</Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>GMV</Text>
                    <Text style={[styles.mStatValue, { color: colors.textPrimary }]}>
                      {formatCurrency(m.total_sales_volume)}
                    </Text>
                  </View>
                  <View style={styles.mStatItem}>
                    <Text style={styles.mStatLabel}>Settled</Text>
                    <Text style={[styles.mStatValue, { color: colors.accentEmerald }]}>
                      {formatCurrency(m.total_collected)}
                    </Text>
                  </View>
                </View>

                {/* Collection Progress Bar */}
                <View style={styles.progressContainer}>
                  <View style={styles.progressLabels}>
                    <Text style={styles.progressLabelText}>Settlement Efficiency</Text>
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
                      <Text style={styles.openTerminalBtnText}>Open Merchant Terminal</Text>
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity style={styles.switchStoreBtn} onPress={() => handleSetActiveStore(m)}>
                      <Text style={styles.switchStoreBtnText}>Switch Store Context</Text>
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
                <Text style={styles.modalTitle}>Onboard Merchant Account</Text>
                <Text style={styles.modalSub}>Register an isolated merchant store context on VoiceLedger</Text>
              </View>
              <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setModalVisible(false)}>
                <X size={18} color={colors.textMuted} />
              </TouchableOpacity>
            </View>

            {formError ? (
              <View style={styles.errorBox}>
                <AlertCircle size={15} color={colors.accentRose} style={{ marginRight: 8 }} />
                <Text style={styles.errorText}>{formError}</Text>
              </View>
            ) : null}

            {/* Store Name Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Store / Business Name *</Text>
              <TextInput
                style={styles.formInput}
                placeholder="e.g. Royal Apparel & Footwear"
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
                  <Text style={styles.submitBtnText}>Create Account</Text>
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
    marginBottom: 24,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 18,
    gap: 16,
    flexWrap: 'wrap',
  },
  titleRowMobile: {
    flexDirection: 'column',
    alignItems: 'stretch',
  },
  mainTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.4,
    marginBottom: 2,
  },
  subTitle: {
    fontSize: 12,
    color: colors.textSecondary,
    maxWidth: 650,
    lineHeight: 16,
  },
  onboardBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#7c3aed',
    paddingVertical: 9,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  onboardBtnText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 12,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  metricsGridMobile: {
    flexDirection: 'column',
    gap: 10,
  },
  kpiCard: {
    backgroundColor: '#111827',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 16,
  },
  kpiQuarter: {
    flex: 1,
    minWidth: 200,
  },
  kpiFull: {
    width: '100%',
  },
  kpiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  kpiIconWrap: {
    width: 26,
    height: 26,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  kpiLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  kpiValue: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  kpiSub: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
  vendorCountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  activePill: {
    backgroundColor: colors.badgePaidBg,
    borderColor: colors.badgePaidBorder,
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  activePillText: {
    color: colors.badgePaidText,
    fontSize: 10,
    fontWeight: '700',
  },
  searchBarContainer: {
    backgroundColor: '#111827',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 14,
    marginBottom: 16,
  },
  searchInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0b0f19',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 10,
    marginBottom: 10,
  },
  searchInput: {
    flex: 1,
    height: 38,
    color: colors.textPrimary,
    fontSize: 12,
  },
  clearSearchBtn: {
    padding: 4,
  },
  clearSearchText: {
    color: colors.textMuted,
    fontSize: 11,
  },
  filterScroll: {
    flexDirection: 'row',
  },
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    marginRight: 6,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  filterChipActive: {
    backgroundColor: 'rgba(124, 58, 237, 0.2)',
    borderColor: '#7c3aed',
  },
  filterChipText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  filterChipTextActive: {
    color: '#c4b5fd',
    fontWeight: '700',
  },
  merchantGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  merchantGridMobile: {
    flexDirection: 'column',
  },
  merchantCard: {
    backgroundColor: '#111827',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 16,
    flex: 1,
    minWidth: 280,
    maxWidth: '49%',
  },
  merchantCardCurrent: {
    borderColor: '#7c3aed',
    backgroundColor: '#131b2e',
  },
  mCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
    gap: 10,
  },
  mStoreInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 10,
  },
  mAvatar: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  mAvatarCurrent: {
    backgroundColor: 'rgba(124, 58, 237, 0.15)',
    borderColor: '#7c3aed',
  },
  mName: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  tagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
    flexWrap: 'wrap',
  },
  catBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  catBadgeText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '500',
  },
  phoneRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  phoneText: {
    color: colors.textMuted,
    fontSize: 10,
  },
  statusPillWrapper: {
    alignItems: 'flex-end',
  },
  currentActivePill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.25)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  currentActiveText: {
    color: '#34d399',
    fontSize: 10,
    fontWeight: '700',
  },
  statusToggle: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.25)',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  statusToggleInactive: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderColor: colors.borderColor,
  },
  statusToggleText: {
    color: colors.badgePaidText,
    fontSize: 10,
    fontWeight: '600',
  },
  statusToggleTextInactive: {
    color: colors.textMuted,
  },
  mStatsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#0b0f19',
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  mStatItem: {
    alignItems: 'center',
  },
  mStatLabel: {
    fontSize: 10,
    color: colors.textMuted,
    marginBottom: 2,
    fontWeight: '500',
  },
  mStatValue: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  progressContainer: {
    marginBottom: 12,
  },
  progressLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  progressLabelText: {
    fontSize: 10,
    color: colors.textMuted,
  },
  progressPercentText: {
    fontSize: 10,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  progressBarBg: {
    height: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.accentEmerald,
    borderRadius: 2,
  },
  mCardActions: {
    marginTop: 2,
  },
  switchStoreBtn: {
    backgroundColor: 'rgba(124, 58, 237, 0.1)',
    borderColor: 'rgba(124, 58, 237, 0.25)',
    borderWidth: 1,
    paddingVertical: 7,
    borderRadius: 6,
    alignItems: 'center',
  },
  switchStoreBtnText: {
    color: '#c4b5fd',
    fontWeight: '600',
    fontSize: 11,
  },
  openTerminalBtn: {
    backgroundColor: '#7c3aed',
    paddingVertical: 7,
    borderRadius: 6,
    alignItems: 'center',
  },
  openTerminalBtnText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 11,
  },
  loadingBox: {
    padding: 40,
    alignItems: 'center',
  },
  loadingText: {
    color: colors.textSecondary,
    marginTop: 8,
    fontSize: 12,
  },
  emptyBox: {
    padding: 40,
    alignItems: 'center',
    backgroundColor: '#111827',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySub: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    backgroundColor: '#111827',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 20,
    width: '100%',
    maxWidth: 480,
  },
  modalCardMobile: {
    maxWidth: '100%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  modalSub: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  modalCloseBtn: {
    padding: 4,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
    borderRadius: 6,
    padding: 8,
    marginBottom: 12,
  },
  errorText: {
    color: '#fb7185',
    fontSize: 12,
  },
  inputGroup: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  formInput: {
    backgroundColor: '#0b0f19',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    height: 38,
    color: colors.textPrimary,
    fontSize: 12,
  },
  catSelectorScroll: {
    flexDirection: 'row',
  },
  catSelectChip: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderColor: colors.borderColor,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginRight: 6,
  },
  catSelectChipActive: {
    backgroundColor: 'rgba(124, 58, 237, 0.2)',
    borderColor: '#7c3aed',
  },
  catSelectChipText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '500',
  },
  catSelectChipTextActive: {
    color: '#c4b5fd',
    fontWeight: '700',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 8,
  },
  cancelBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  cancelBtnText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  submitBtn: {
    backgroundColor: '#7c3aed',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
    alignItems: 'center',
  },
  submitBtnText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 12,
  },
});
