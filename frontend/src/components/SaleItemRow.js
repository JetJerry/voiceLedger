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
  let statusLabel = 'PENDING';

  if (sale.status === 'PAID') {
    badgeStyle = styles.badgePaid;
    badgeTextStyle = styles.badgePaidText;
    statusLabel = 'PAID';
  } else if (sale.status === 'PARTIAL') {
    badgeStyle = styles.badgePartial;
    badgeTextStyle = styles.badgePartialText;
    statusLabel = 'PARTIAL';
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
          <View style={styles.metaRow}>
            <Text style={styles.saleId}>Ref #{sale.id.slice(0, 8)}</Text>
            {sale.customer_name && (
              <>
                <Text style={styles.metaDot}>•</Text>
                <Text style={styles.customerName}>{sale.customer_name}</Text>
              </>
            )}
          </View>
        </View>
        <View style={[styles.badge, badgeStyle]}>
          <Text style={[styles.badgeText, badgeTextStyle]}>{statusLabel}</Text>
        </View>
      </View>

      <View style={styles.financialRow}>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Order Total</Text>
          <Text style={styles.finValue}>₹{sale.total_amount.toFixed(2)}</Text>
        </View>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Settled</Text>
          <Text style={[styles.finValue, { color: colors.accentEmerald }]}>
            ₹{sale.received_amount.toFixed(2)}
          </Text>
        </View>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>Balance Due</Text>
          <Text style={[styles.finValue, sale.outstanding_amount > 0 ? { color: colors.accentRose } : { color: colors.textSecondary }]}>
            ₹{sale.outstanding_amount.toFixed(2)}
          </Text>
        </View>
      </View>

      <View style={styles.actionsRow}>
        {sale.razorpay_payment_link_url ? (
          <TouchableOpacity style={styles.btnRzp} onPress={handleOpenRzpLink} activeOpacity={0.8}>
            <ExternalLink size={13} color="#a5b4fc" style={{ marginRight: 5 }} />
            <Text style={styles.btnRzpText}>Payment Link</Text>
          </TouchableOpacity>
        ) : null}

        {sale.status !== 'PAID' ? (
          <TouchableOpacity
            style={styles.btnSim}
            onPress={() => onSimulatePayment(sale)}
            activeOpacity={0.8}
          >
            <Zap size={13} color="#ffffff" style={{ marginRight: 5 }} />
            <Text style={styles.btnSimText}>Simulate Settlement</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#0d131f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: 10,
    padding: 14,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  infoCol: {
    flex: 1,
    marginRight: 10,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 3,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  saleId: {
    fontSize: 11,
    color: colors.textMuted,
    fontFamily: 'monospace',
  },
  metaDot: {
    color: colors.textMuted,
    marginHorizontal: 6,
    fontSize: 10,
  },
  customerName: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
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
    backgroundColor: '#080c14',
    borderRadius: 8,
    padding: 10,
    justifyContent: 'space-around',
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.03)',
  },
  finCol: {
    alignItems: 'center',
  },
  finLabel: {
    fontSize: 10,
    color: colors.textMuted,
    marginBottom: 2,
    fontWeight: '500',
  },
  finValue: {
    fontSize: 13,
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
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.25)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  btnRzpText: {
    fontSize: 11,
    color: '#a5b4fc',
    fontWeight: '600',
  },
  btnSim: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  btnSimText: {
    fontSize: 11,
    color: '#ffffff',
    fontWeight: '600',
  },
});
