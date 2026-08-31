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
import {
  RefreshCw,
  ShoppingCart,
  Download,
  Calendar,
  DollarSign,
  Clock,
  CheckCircle2,
  Search,
  FileSpreadsheet,
  PackageOpen,
  Filter,
} from 'lucide-react-native';
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
          <Text style={styles.title}>Sales & Payment Settlement Ledger</Text>
          <Text style={styles.subtitle}>
            Comprehensive transaction ledger with period analytics and structured spreadsheet exports.
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
                <FileSpreadsheet size={15} color="#ffffff" style={{ marginRight: 6 }} />
                <Text style={styles.exportBtnText}>Export Excel (.xlsx)</Text>
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
              size={13}
              color={colors.textSecondary}
              style={isRefreshing ? styles.spinning : null}
            />
            <Text style={styles.refreshText}>Refresh</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 2. Period Switcher Tabs & Analytics Card */}
      <View style={styles.periodTabsCard}>
        <View style={styles.periodTabsRow}>
          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'today' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('today')}
          >
            <Calendar size={13} color={selectedPeriod === 'today' ? '#ffffff' : colors.textMuted} style={{ marginRight: 5 }} />
            <Text style={[styles.periodTabText, selectedPeriod === 'today' && styles.periodTabTextActive]}>
              Today
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'week' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('week')}
          >
            <Calendar size={13} color={selectedPeriod === 'week' ? '#ffffff' : colors.textMuted} style={{ marginRight: 5 }} />
            <Text style={[styles.periodTabText, selectedPeriod === 'week' && styles.periodTabTextActive]}>
              This Week (7D)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'month' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('month')}
          >
            <Calendar size={13} color={selectedPeriod === 'month' ? '#ffffff' : colors.textMuted} style={{ marginRight: 5 }} />
            <Text style={[styles.periodTabText, selectedPeriod === 'month' && styles.periodTabTextActive]}>
              This Month (30D)
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.periodTab, selectedPeriod === 'all_time' && styles.periodTabActive]}
            onPress={() => setSelectedPeriod('all_time')}
          >
            <Calendar size={13} color={selectedPeriod === 'all_time' ? '#ffffff' : colors.textMuted} style={{ marginRight: 5 }} />
            <Text style={[styles.periodTabText, selectedPeriod === 'all_time' && styles.periodTabTextActive]}>
              All-Time
            </Text>
          </TouchableOpacity>
        </View>

        {/* Period Financial Stat Cards */}
        <View style={[styles.metricsRow, isMobile && styles.metricsRowMobile]}>
          {/* GMV */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Gross Merchandise Value</Text>
              <DollarSign size={15} color={colors.primary} />
            </View>
            <Text style={styles.metricValue}>₹{currentStats.total_gmv?.toFixed(2) || '0.00'}</Text>
            <Text style={styles.metricSub}>{currentStats.orders_count || 0} Orders Recorded</Text>
          </View>

          {/* Collected */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Settled Collections</Text>
              <CheckCircle2 size={15} color={colors.accentEmerald} />
            </View>
            <Text style={[styles.metricValue, { color: colors.accentEmerald }]}>
              ₹{currentStats.total_collected?.toFixed(2) || '0.00'}
            </Text>
            <Text style={styles.metricSub}>{currentStats.collection_rate || 100}% Collection Efficiency</Text>
          </View>

          {/* Outstanding */}
          <View style={styles.metricCard}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricLabel}>Outstanding Receivables</Text>
              <Clock size={15} color={colors.accentAmber} />
            </View>
            <Text style={[styles.metricValue, { color: colors.accentAmber }]}>
              ₹{currentStats.total_outstanding?.toFixed(2) || '0.00'}
            </Text>
            <Text style={styles.metricSub}>{currentStats.pending_orders_count || 0} Pending Settlement</Text>
          </View>
        </View>

        {/* Top Selling Products Bar */}
        {currentStats.top_products?.length > 0 && (
          <View style={styles.topProductsWrap}>
            <Text style={styles.topProductsTitle}>Top Volume Products in Period:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 6 }}>
              {currentStats.top_products.map((tp, idx) => (
                <View key={idx} style={styles.topProductChip}>
                  <Text style={styles.topProductRank}>#{idx + 1}</Text>
                  <Text style={styles.topProductName}>{tp.name.charAt(0).toUpperCase() + tp.name.slice(1)}</Text>
                  <Text style={styles.topProductVol}>{tp.units} units</Text>
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
            <ShoppingCart size={16} color={colors.primary} style={{ marginRight: 8 }} />
            <Text style={styles.sectionTitle}>Transaction Records</Text>
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
          <Search size={15} color={colors.textMuted} style={{ marginRight: 8 }} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by customer name, product item, or transaction ID..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={{ padding: 4 }}>
              <Text style={{ color: colors.textMuted, fontSize: 12 }}>Clear</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Sales List */}
        <View style={styles.listContainer}>
          {filteredSales.length === 0 ? (
            <View style={styles.emptyContainer}>
              <PackageOpen size={32} color={colors.textMuted} style={{ marginBottom: 8 }} />
              <Text style={styles.emptyTitle}>No transaction records found</Text>
              <Text style={styles.emptySubtitle}>
                No orders match your filter criteria. Record a sale or adjust filters to view transactions.
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
    marginBottom: 24,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
    gap: 16,
  },
  headerRowMobile: {
    flexDirection: 'column',
    alignItems: 'stretch',
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.4,
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    maxWidth: 600,
    lineHeight: 16,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#059669',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  exportBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
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
  periodTabsCard: {
    backgroundColor: '#111827',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 18,
    marginBottom: 16,
  },
  periodTabsRow: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 8,
    padding: 3,
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginBottom: 14,
  },
  periodTab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 7,
    borderRadius: 6,
  },
  periodTabActive: {
    backgroundColor: colors.primary,
  },
  periodTabText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
  },
  periodTabTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  metricsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  metricsRowMobile: {
    flexDirection: 'column',
    gap: 10,
  },
  metricCard: {
    flex: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
  },
  metricHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  metricLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.3,
  },
  metricSub: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
  topProductsWrap: {
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  topProductsTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
    marginBottom: 4,
  },
  topProductChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginRight: 8,
  },
  topProductRank: {
    fontSize: 10,
    fontWeight: '800',
    color: colors.primary,
    marginRight: 6,
  },
  topProductName: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textPrimary,
    marginRight: 8,
  },
  topProductVol: {
    fontSize: 10,
    color: colors.textMuted,
    marginRight: 8,
  },
  topProductRev: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.accentEmerald,
  },
  sectionCard: {
    backgroundColor: '#111827',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 18,
  },
  ledgerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
    flexWrap: 'wrap',
    gap: 10,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textPrimary,
    marginRight: 8,
  },
  countPill: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  countPillText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  statusChipsRow: {
    flexDirection: 'row',
    gap: 6,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  statusChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
  },
  statusChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0b0f19',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 14,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 12,
  },
  listContainer: {
    gap: 10,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 36,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySubtitle: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 400,
  },
});
