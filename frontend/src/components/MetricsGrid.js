import React from 'react';
import { View, Text, StyleSheet, useWindowDimensions } from 'react-native';
import { colors } from '../theme/colors';

export default function MetricsGrid({ summary }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const todaySales = summary ? summary.today_sales || 0 : 0;
  const collected = summary ? summary.total_collected || 0 : 0;
  const outstanding = summary ? summary.total_outstanding || 0 : 0;
  const paidCount = summary ? summary.paid_count || 0 : 0;
  const partialCount = summary ? summary.partial_count || 0 : 0;
  const pendingCount = summary ? summary.pending_count || 0 : 0;

  const formatCurrency = (num) => {
    return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <View style={[styles.gridContainer, isMobile && styles.gridMobile]}>
      {/* 1. Today's Sales */}
      <View style={[styles.metricCard, isMobile ? styles.cardFullWidth : styles.cardQuarter]}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardEmoji}>💰</Text>
          <Text style={styles.cardLabel}>Today's Sales</Text>
        </View>
        <Text style={styles.cardValue}>{formatCurrency(todaySales)}</Text>
      </View>

      {/* 2. Total Collected */}
      <View style={[styles.metricCard, isMobile ? styles.cardFullWidth : styles.cardQuarter]}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardEmoji}>✅</Text>
          <Text style={styles.cardLabel}>Total Collected</Text>
        </View>
        <Text style={[styles.cardValue, { color: colors.accentEmerald }]}>
          {formatCurrency(collected)}
        </Text>
      </View>

      {/* 3. Total Outstanding */}
      <View style={[styles.metricCard, isMobile ? styles.cardFullWidth : styles.cardQuarter]}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardEmoji}>⚠️</Text>
          <Text style={styles.cardLabel}>Total Outstanding</Text>
        </View>
        <Text style={[styles.cardValue, { color: colors.accentRose }]}>
          {formatCurrency(outstanding)}
        </Text>
      </View>

      {/* 4. Transactions Counts */}
      <View style={[styles.metricCard, isMobile ? styles.cardFullWidth : styles.cardQuarter]}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardEmoji}>📊</Text>
          <Text style={styles.cardLabel}>Transactions Status</Text>
        </View>
        <View style={styles.badgeRow}>
          <View style={[styles.statusBadge, styles.badgePaid]}>
            <Text style={styles.badgePaidText}><Text style={{ fontWeight: '800' }}>{paidCount}</Text> Paid</Text>
          </View>
          <View style={[styles.statusBadge, styles.badgePartial]}>
            <Text style={styles.badgePartialText}><Text style={{ fontWeight: '800' }}>{partialCount}</Text> Partial</Text>
          </View>
          <View style={[styles.statusBadge, styles.badgePending]}>
            <Text style={styles.badgePendingText}><Text style={{ fontWeight: '800' }}>{pendingCount}</Text> Pending</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
    marginBottom: 24,
  },
  gridMobile: {
    flexDirection: 'column',
    gap: 12,
  },
  metricCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 18,
  },
  cardQuarter: {
    flex: 1,
    minWidth: 200,
  },
  cardFullWidth: {
    width: '100%',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  cardEmoji: {
    fontSize: 18,
    marginRight: 8,
  },
  cardLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  cardValue: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.5,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
    flexWrap: 'wrap',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
  },
  badgePaid: {
    backgroundColor: colors.badgePaidBg,
    borderColor: colors.badgePaidBorder,
  },
  badgePaidText: {
    color: colors.badgePaidText,
    fontSize: 11,
  },
  badgePartial: {
    backgroundColor: colors.badgePartialBg,
    borderColor: colors.badgePartialBorder,
  },
  badgePartialText: {
    color: colors.badgePartialText,
    fontSize: 11,
  },
  badgePending: {
    backgroundColor: colors.badgePendingBg,
    borderColor: colors.badgePendingBorder,
  },
  badgePendingText: {
    color: colors.badgePendingText,
    fontSize: 11,
  },
});
