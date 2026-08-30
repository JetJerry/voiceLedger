import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking } from 'react-native';
import { CreditCard, Zap, ExternalLink } from 'lucide-react-native';
import { colors } from '../theme/colors';

export default function SaleItemRow({ sale, onSimulatePayment }) {
  const itemsSummary = (sale.items && sale.items.length > 0)
    ? sale.items.map(i => `${i.quantity}x ${i.product_name}`).join(', ')
    : (sale.raw_voice_transcript || 'Order items');

  let badgeStyle = styles.badgePending;
  let badgeTextStyle = styles.badgePendingText;
  let statusLabel = 'PENDING ⏳';

  if (sale.status === 'PAID') {
    badgeStyle = styles.badgePaid;
    badgeTextStyle = styles.badgePaidText;
    statusLabel = 'PAID ✅';
  } else if (sale.status === 'PARTIAL') {
    badgeStyle = styles.badgePartial;
    badgeTextStyle = styles.badgePartialText;
    statusLabel = 'PARTIAL ⚠️';
  }

  const handleOpenRzpLink = () => {
    if (sale.razorpay_payment_link_url) {
      Linking.openURL(sale.razorpay_payment_link_url);
    }
  };

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.infoCol}>
          <Text style={styles.itemTitle}>{itemsSummary}</Text>
          <Text style={styles.saleId}>Sale #{sale.id.slice(0, 8)}</Text>
        </View>
        <View style={[styles.badge, badgeStyle]}>
          <Text style={[styles.badgeText, badgeTextStyle]}>{statusLabel}</Text>
        </View>
      </View>

      <View style={styles.financialRow}>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Expected</Text>
          <Text style={styles.finValue}>₹{sale.total_amount.toFixed(2)}</Text>
        </View>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Received</Text>
          <Text style={[styles.finValue, { color: colors.accentEmerald }]}>
            ₹{sale.received_amount.toFixed(2)}
          </Text>
        </View>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Outstanding</Text>
          <Text style={[styles.finValue, sale.outstanding_amount > 0 && { color: colors.accentRose }]}>
            ₹{sale.outstanding_amount.toFixed(2)}
          </Text>
        </View>
      </View>

      <View style={styles.actionsRow}>
        {sale.razorpay_payment_link_url ? (
          <TouchableOpacity style={styles.btnRzp} onPress={handleOpenRzpLink} activeOpacity={0.8}>
            <CreditCard size={14} color="#a5b4fc" style={{ marginRight: 6 }} />
            <Text style={styles.btnRzpText}>Pay Link</Text>
          </TouchableOpacity>
        ) : null}

        {sale.status !== 'PAID' ? (
          <TouchableOpacity
            style={styles.btnSim}
            onPress={() => onSimulatePayment(sale)}
            activeOpacity={0.8}
          >
            <Zap size={14} color="#ffffff" style={{ marginRight: 6 }} />
            <Text style={styles.btnSimText}>Pay Simulate</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  infoCol: {
    flex: 1,
    marginRight: 10,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  saleId: {
    fontSize: 11,
    color: colors.textMuted,
    fontFamily: 'monospace',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  badgePaid: {
    backgroundColor: colors.badgePaidBg,
    borderColor: colors.badgePaidBorder,
  },
  badgePaidText: {
    color: colors.badgePaidText,
  },
  badgePartial: {
    backgroundColor: colors.badgePartialBg,
    borderColor: colors.badgePartialBorder,
  },
  badgePartialText: {
    color: colors.badgePartialText,
  },
  badgePending: {
    backgroundColor: colors.badgePendingBg,
    borderColor: colors.badgePendingBorder,
  },
  badgePendingText: {
    color: colors.badgePendingText,
  },
  financialRow: {
    flexDirection: 'row',
    backgroundColor: 'rgba(10, 14, 23, 0.5)',
    borderRadius: 10,
    padding: 10,
    justifyContent: 'space-around',
    marginBottom: 12,
  },
  finCol: {
    alignItems: 'center',
  },
  finLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginBottom: 2,
  },
  finValue: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
  btnRzp: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.3)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  btnRzpText: {
    fontSize: 12,
    color: '#c7d2fe',
    fontWeight: '600',
  },
  btnSim: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  btnSimText: {
    fontSize: 12,
    color: '#ffffff',
    fontWeight: '600',
  },
});
