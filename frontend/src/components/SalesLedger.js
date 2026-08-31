import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  useWindowDimensions,
  Platform,
} from 'react-native';
import { RefreshCw, ShoppingCart, Download, TrendingUp, DollarSign, Clock, CheckCircle2 } from 'lucide-react-native';
import { colors } from '../theme/colors';
import { apiService } from '../services/apiService';
import SaleItemRow from './SaleItemRow';

export default function SalesLedger({ sales = [], onRefresh, onSimulatePayment, isRefreshing }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  // Selected period: 'today' | 'week' | 'month' | 'all_time'
  const [selectedPeriod, setSelectedPeriod] = useState('month');
  const [analytics, setAnalytics] = useState(null);
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Filters for transactions list
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const loadAnalytics = useCallback(async () => {
    try {
      setIsLoadingAnalytics(true);
      const data = await apiService.getSalesAnalytics();
      setAnalytics(data);
    } catch (e) {
      console.warn('Failed to load sales analytics:', e.message);
    } finally {
      setIsLoadingAnalytics(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics, sales]);

  const handleExportExcel = () => {
    setIsExporting(true);
    try {
      const exportUrl = apiService.getExportExcelUrl();
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        const link = document.createElement('a');
        link.href = exportUrl;
        link.setAttribute('download', 'VoiceLedger_Sales_Report.xlsx');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        alert(`Export ready: ${exportUrl}`);
      }
    } catch (e) {
      alert(`Export failed: ${e.message}`);
    } finally {
      setTimeout(() => setIsExporting(false), 1000);
    }
  };

  const currentStats = analytics?.periods?.[selectedPeriod] || {
    orders_count: 0,
    total_gmv: 0,
    total_collected: 0,
    total_outstanding: 0,
    paid_orders_count: 0,
    collection_rate: 100,
    top_products: [],
  };

  // Filter transactions
  const filteredSales = (sales || []).filter((s) => {
    if (statusFilter !== 'ALL' && s.status !== statusFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchCustomer = (s.customer_name || '').toLowerCase().includes(q);
      const matchId = (s.id || '').toLowerCase().includes(q);
      const matchItem = (s.items || []).some((it) => (it.product_name || '').toLowerCase().includes(q));
      return matchCustomer || matchId || matchItem;
    }
    return true;
  });

  return (
    <View style={styles.container}>
      {/* 1. Header Bar */}
      <View style={[styles.headerRow, isMobile && styles.headerRowMobile]}>
        <View style={{ flex: 1 }}>
          <View style={styles.badgeHub}>
            <Text style={styles.badgeHubText}>📈 Sales Analytics & Ledger</Text>
          </View>
          <Text style={styles.title}>Sales & Payment Ledger</Text>
          <Text style={styles.subtitle}>
            Monitor your daily, weekly, and monthly store revenue and export formatted Excel sheets.
          </Text>
        </View>

        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.exportBtn}
            onPress={handleExportExcel}
            disabled={isExporting}
            activeOpacity={0.8}
          >
            {isExporting ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Download size={16} color="#ffffff" />
                <Text style={styles.exportBtnText}>📊 Export Excel (.xlsx)</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.refreshBtn}
            onPress={() => {
              if (onRefresh) onRefresh();
              loadAnalytics();
            }}
            disabled={isRefreshing}
            activeOpacity={0.7}
          >
            <RefreshCw
              size={14}
              color={colors.textSecondary}
              style={isRefreshing ? styles.spinning : null}
            />
            <Text style={styles.refreshText}>Refresh</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 2. Period Switcher Tabs */}
      <View style={styles.periodTabsCard}>
        <View style={styles.periodTabsRow}>
          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'today' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('today')}
          >
            <Text style={[styles.periodTabText, selectedPeriod === 'today' && styles.periodTabTextActive]}>
              📅 Today (Day)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'week' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('week')}
          >
            <Text style={[styles.periodTabText, selectedPeriod === 'week' && styles.periodTabTextActive]}>
              📅 This Week (7 Days)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'month' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('month')}
          >
            <Text style={[styles.periodTabText, selectedPeriod === 'month' && styles.periodTabTextActive]}>
              📅 This Month (30 Days)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'all_time' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('all_time')}
          >
            <Text style={[styles.periodTabText, selectedPeriod === 'all_time' && styles.periodTabTextActive]}>
              🏆 All Time Total
            </Text>
          </TouchableOpacity>
        </View>

        {/* Period Financial Stat Cards */}
        <View style={[styles.metricsRow, isMobile && styles.metricsRowMobile]}>
          {/* GMV */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Gross Sales (GMV)</Text>
              <DollarSign size={16} color={colors.primary} />
            </View>
            <Text style={styles.metricValue}>₹{currentStats.total_gmv?.toFixed(2) || '0.00'}</Text>
            <Text style={styles.metricSub}>{currentStats.orders_count || 0} Orders Placed</Text>
          </View>

          {/* Collected */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Collected Payment</Text>
              <CheckCircle2 size={16} color={colors.accentEmerald} />
            </View>
            <Text style={[styles.metricValue, { color: colors.accentEmerald }]}>
              ₹{currentStats.total_collected?.toFixed(2) || '0.00'}
            </Text>
            <Text style={styles.metricSub}>{currentStats.collection_rate || 100}% Collection Rate</Text>
          </View>

          {/* Outstanding */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Outstanding / Pending</Text>
              <Clock size={16} color={colors.accentAmber} />
            </View>
            <Text style={[styles.metricValue, { color: colors.accentAmber }]}>
              ₹{currentStats.total_outstanding?.toFixed(2) || '0.00'}
            </Text>
            <Text style={styles.metricSub}>{currentStats.pending_orders_count || 0} Unpaid Orders</Text>
          </View>
        </View>

        {/* Top Selling Products Bar */}
        {currentStats.top_products?.length > 0 && (
          <View style={styles.topProductsWrap}>
            <Text style={styles.topProductsTitle}>🔥 Top Selling Items in this Period:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 6 }}>
              {currentStats.top_products.map((tp, idx) => (
                <View key={idx} style={styles.topProductChip}>
                  <Text style={styles.topProductRank}>#{idx + 1}</Text>
                  <Text style={styles.topProductName}>{tp.name.charAt(0).toUpperCase() + tp.name.slice(1)}</Text>
                  <Text style={styles.topProductVol}>{tp.units} sold</Text>
                  <Text style={styles.topProductRev}>₹{tp.revenue.toFixed(2)}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        )}
      </View>

      {/* 3. Detailed Transactions Ledger Section */}
      <View style={styles.sectionCard}>
        <View style={styles.ledgerHeader}>
          <View style={styles.titleWrap}>
            <ShoppingCart size={18} color={colors.primary} style={{ marginRight: 8 }} />
            <Text style={styles.sectionTitle}>Recorded Orders & Payments</Text>
            <View style={styles.countPill}>
              <Text style={styles.countPillText}>{filteredSales.length}</Text>
            </View>
          </View>

          {/* Status Filter Chips */}
          <View style={styles.statusChipsRow}>
            {['ALL', 'PAID', 'PENDING', 'PARTIAL'].map((st) => (
              <TouchableOpacity
                key={st}
                style={[styles.statusChip, statusFilter === st && styles.statusChipActive]}
                onPress={() => setStatusFilter(st)}
              >
                <Text style={[styles.statusChipText, statusFilter === st && styles.statusChipTextActive]}>
                  {st}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Search Bar */}
        <View style={styles.searchBar}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            style={styles.searchInput}
            placeholder="Search by customer name, product item, or sale ID..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={{ padding: 6 }}>
              <Text style={{ color: colors.textMuted }}>✕</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Sales List */}
        <View style={styles.listContainer}>
          {filteredSales.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyEmoji}>📦</Text>
              <Text style={styles.emptyTitle}>No orders matching filter</Text>
              <Text style={styles.emptySubtitle}>
                Speak a sale (e.g. "2 coffee 60 rupaye") or adjust filters to view transactions.
              </Text>
            </View>
          ) : (
            filteredSales.map((sale) => (
              <SaleItemRow
                key={sale.id}
                sale={sale}
                onSimulatePayment={onSimulatePayment}
              />
            ))
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    marginBottom: 32,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
    gap: 16,
  },
  headerRowMobile: {
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
    marginBottom: 6,
  },
  badgeHubText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    maxWidth: 600,
    lineHeight: 18,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#059669',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 8,
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  exportBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '800',
  },
  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  refreshText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  spinning: {
    transform: [{ rotate: '45deg' }],
  },

  // Period Switcher Card
  periodTabsCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 18,
    marginBottom: 24,
  },
  periodTabsRow: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: 12,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  periodTab: {
    flex: 1,
    minWidth: 110,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  periodTabActive: {
    backgroundColor: colors.primary,
  },
  periodTabText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textMuted,
  },
  periodTabTextActive: {
    color: '#ffffff',
  },

  // Metrics Grid
  metricsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  metricsRowMobile: {
    flexDirection: 'column',
  },
  metricCard: {
    flex: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.06)',
    padding: 14,
  },
  metricHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  metricLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 20,
    fontWeight: '900',
    color: colors.textPrimary,
    letterSpacing: -0.5,
    marginBottom: 2,
  },
  metricSub: {
    fontSize: 11,
    color: colors.textMuted,
  },

  // Top Products
  topProductsWrap: {
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.06)',
  },
  topProductsTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  topProductChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 8,
    gap: 6,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  topProductRank: {
    color: colors.primary,
    fontWeight: '800',
    fontSize: 11,
  },
  topProductName: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 12,
  },
  topProductVol: {
    color: colors.textMuted,
    fontSize: 11,
  },
  topProductRev: {
    color: colors.accentEmerald,
    fontWeight: '700',
    fontSize: 11,
  },

  // Ledger Section
  sectionCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 20,
  },
  ledgerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
    flexWrap: 'wrap',
    gap: 10,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  countPill: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginLeft: 8,
  },
  countPillText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  statusChipsRow: {
    flexDirection: 'row',
    gap: 6,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  statusChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
  },
  statusChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },

  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  searchIcon: {
    fontSize: 14,
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    height: 40,
    color: colors.textPrimary,
    fontSize: 13,
  },

  listContainer: {
    width: '100%',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 36,
  },
  emptyEmoji: {
    fontSize: 36,
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySubtitle: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 320,
    lineHeight: 16,
  },
});
