import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { RefreshCw, ShoppingCart } from 'lucide-react-native';
import { colors } from '../theme/colors';
import SaleItemRow from './SaleItemRow';

export default function SalesLedger({ sales, onRefresh, onSimulatePayment, isRefreshing }) {
  return (
    <View style={styles.sectionCard}>
      {/* Section Header */}
      <View style={styles.sectionHeader}>
        <View style={styles.titleWrap}>
          <ShoppingCart size={20} color={colors.primary} style={{ marginRight: 8 }} />
          <Text style={styles.sectionTitle}>Sold Products & Payment Status</Text>
        </View>

        <TouchableOpacity
          style={styles.refreshBtn}
          onPress={onRefresh}
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

      {/* Sales List */}
      <View style={styles.listContainer}>
        {(!sales || sales.length === 0) ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyEmoji}>📦</Text>
            <Text style={styles.emptyTitle}>No sales recorded yet</Text>
            <Text style={styles.emptySubtitle}>
              Tap the mic above and speak a sale (e.g. "2 coffee 60 rupaye") to start!
            </Text>
          </View>
        ) : (
          sales.map((sale) => (
            <SaleItemRow
              key={sale.id}
              sale={sale}
              onSimulatePayment={onSimulatePayment}
            />
          ))
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  sectionCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
    marginBottom: 32,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    letterSpacing: -0.3,
  },
  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    paddingVertical: 7,
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
  listContainer: {
    marginTop: 4,
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
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySubtitle: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 320,
  },
});
