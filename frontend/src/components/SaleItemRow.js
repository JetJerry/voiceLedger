import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking, Platform } from 'react-native';
import {
  CreditCard,
  Zap,
  ExternalLink,
  CheckCircle2,
  Clock,
  AlertCircle,
  Calendar,
  User,
  ChevronDown,
  ChevronUp,
  Receipt,
  Volume2,
  Copy,
  Check,
} from 'lucide-react-native';
import { colors } from '../theme/colors';
import { voiceService } from '../services/voiceService';

export default function SaleItemRow({ sale, onSimulatePayment }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  // Format Date and Time
  const formatDateTime = (dateString) => {
    if (!dateString) return 'Just now';
    try {
      const d = new Date(dateString);
      if (isNaN(d.getTime())) return dateString;
      
      const now = new Date();
      const isToday = d.toDateString() === now.toDateString();
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
      
      if (isToday) {
        return `Today • ${timeStr}`;
      }
      
      const dateStr = d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
      });
      return `${dateStr} • ${timeStr}`;
    } catch {
      return dateString;
    }
  };

  const hasItems = sale.items && sale.items.length > 0;
  const itemsCount = hasItems ? sale.items.length : 0;
  
  const itemsSummary = hasItems
    ? sale.items.map((i) => `${i.quantity}x ${i.product_name}`).join(', ')
    : sale.raw_voice_transcript || 'Recorded Order';

  const isPaid = sale.status === 'PAID';
  const isPartial = sale.status === 'PARTIAL';
  const isPending = sale.status === 'PENDING' || (!isPaid && !isPartial);

  const handleOpenRzpLink = () => {
    if (sale.razorpay_payment_link_url) {
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.open(sale.razorpay_payment_link_url, '_blank');
      } else {
        Linking.openURL(sale.razorpay_payment_link_url);
      }
    }
  };

  const handleCopyRzpLink = () => {
    if (sale.razorpay_payment_link_url && typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(sale.razorpay_payment_link_url);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  const handleReplayVoice = () => {
    const text = `Payment settled: ${sale.customer_name || 'Customer'} ka Rs. ${sale.received_amount.toFixed(2)} receive ho chuka hai.`;
    voiceService.playTTSAudio(null, text);
  };

  return (
    <View style={[styles.card, isPaid && styles.cardPaid, isPartial && styles.cardPartial]}>
      {/* 1. Card Top Bar: Reference ID, Date/Time & Status Badge */}
      <View style={styles.topRow}>
        <View style={styles.topLeft}>
          <View style={styles.refBadge}>
            <Text style={styles.refText}>#{sale.id ? sale.id.slice(0, 10).toUpperCase() : 'ORDER'}</Text>
          </View>
          <View style={styles.timeBadge}>
            <Calendar size={12} color={colors.textSecondary} style={{ marginRight: 4 }} />
            <Text style={styles.timeText}>{formatDateTime(sale.created_at)}</Text>
          </View>
        </View>

        {/* Status Pill Badge */}
        {isPaid ? (
          <View style={styles.badgePaid}>
            <CheckCircle2 size={13} color="#047857" style={{ marginRight: 4 }} />
            <Text style={styles.badgePaidText}>PAID & SETTLED</Text>
          </View>
        ) : isPartial ? (
          <View style={styles.badgePartial}>
            <Clock size={13} color="#b45309" style={{ marginRight: 4 }} />
            <Text style={styles.badgePartialText}>PARTIALLY PAID</Text>
          </View>
        ) : (
          <View style={styles.badgePending}>
            <AlertCircle size={13} color="#b91c1c" style={{ marginRight: 4 }} />
            <Text style={styles.badgePendingText}>PAYMENT PENDING</Text>
          </View>
        )}
      </View>

      {/* 2. Order Summary & Customer Tag */}
      <View style={styles.orderInfoSection}>
        <View style={styles.titleRow}>
          <Text style={styles.itemTitle}>{itemsSummary}</Text>
        </View>

        <View style={styles.tagsRow}>
          {/* Customer Avatar Tag */}
          <View style={styles.customerTag}>
            <User size={12} color={colors.primary} style={{ marginRight: 4 }} />
            <Text style={styles.customerText}>
              {sale.customer_name && sale.customer_name.trim() ? sale.customer_name : 'Walk-in Customer'}
            </Text>
          </View>

          {/* Spoken Voice Note if available */}
          {sale.raw_voice_transcript && (
            <View style={styles.voiceNoteTag}>
              <Text style={styles.voiceNoteText} numberOfLines={1}>
                "{sale.raw_voice_transcript}"
              </Text>
            </View>
          )}
        </View>

        {/* Item Pills */}
        {hasItems && (
          <View style={styles.itemPillsRow}>
            {sale.items.map((item, idx) => (
              <View key={item.id || idx} style={styles.itemPill}>
                <Text style={styles.itemPillText}>
                  <Text style={{ fontWeight: '700', color: colors.primary }}>{item.quantity}x</Text> {item.product_name} (₹{item.unit_price?.toFixed(2)})
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* 3. High-Contrast, Crystal-Clear Financial Summary Row */}
      <View style={styles.financialRow}>
        <View style={styles.finCol}>
          <Text style={styles.finLabel}>TOTAL BILL</Text>
          <Text style={styles.finValueTotal}>₹{sale.total_amount ? sale.total_amount.toFixed(2) : '0.00'}</Text>
        </View>

        <View style={styles.finDivider} />

        <View style={styles.finCol}>
          <Text style={styles.finLabel}>SETTLED (RECEIVED)</Text>
          <Text style={styles.finValueSettled}>₹{sale.received_amount ? sale.received_amount.toFixed(2) : '0.00'}</Text>
        </View>

        <View style={styles.finDivider} />

        <View style={styles.finCol}>
          <Text style={styles.finLabel}>BALANCE DUE</Text>
          <Text style={sale.outstanding_amount > 0 ? styles.finValueDue : styles.finValueZero}>
            ₹{sale.outstanding_amount ? sale.outstanding_amount.toFixed(2) : '0.00'}
          </Text>
        </View>
      </View>

      {/* 4. Expandable Receipt Breakdown Table */}
      {hasItems && (
        <View style={styles.expandableWrap}>
          <TouchableOpacity
            style={styles.expandToggle}
            onPress={() => setIsExpanded(!isExpanded)}
            activeOpacity={0.7}
          >
            <Receipt size={13} color={colors.primary} style={{ marginRight: 5 }} />
            <Text style={styles.expandToggleText}>
              {isExpanded ? 'Hide Itemized Receipt' : `View Itemized Receipt (${itemsCount} ${itemsCount === 1 ? 'item' : 'items'})`}
            </Text>
            {isExpanded ? (
              <ChevronUp size={14} color={colors.primary} style={{ marginLeft: 4 }} />
            ) : (
              <ChevronDown size={14} color={colors.primary} style={{ marginLeft: 4 }} />
            )}
          </TouchableOpacity>

          {isExpanded && (
            <View style={styles.receiptTable}>
              <View style={styles.tableHeader}>
                <Text style={[styles.thText, { flex: 2 }]}>Item Description</Text>
                <Text style={[styles.thText, { flex: 1, textAlign: 'center' }]}>Qty</Text>
                <Text style={[styles.thText, { flex: 1, textAlign: 'right' }]}>Rate</Text>
                <Text style={[styles.thText, { flex: 1, textAlign: 'right' }]}>Amount</Text>
              </View>
              {sale.items.map((it, idx) => (
                <View key={it.id || idx} style={styles.tableRow}>
                  <Text style={[styles.tdText, styles.tdName, { flex: 2 }]}>{it.product_name}</Text>
                  <Text style={[styles.tdText, { flex: 1, textAlign: 'center' }]}>{it.quantity}</Text>
                  <Text style={[styles.tdText, { flex: 1, textAlign: 'right' }]}>₹{it.unit_price?.toFixed(2)}</Text>
                  <Text style={[styles.tdText, styles.tdSubtotal, { flex: 1, textAlign: 'right' }]}>
                    ₹{it.subtotal ? it.subtotal.toFixed(2) : (it.quantity * it.unit_price).toFixed(2)}
                  </Text>
                </View>
              ))}
              <View style={styles.tableFooter}>
                <Text style={styles.tfLabel}>Order Total:</Text>
                <Text style={styles.tfValue}>₹{sale.total_amount?.toFixed(2)}</Text>
              </View>
            </View>
          )}
        </View>
      )}

      {/* 5. Action Buttons & Quick Controls */}
      <View style={styles.actionsRow}>
        {/* Replay Voice button for paid sales */}
        {isPaid && (
          <TouchableOpacity
            style={styles.btnVoiceReplay}
            onPress={handleReplayVoice}
            activeOpacity={0.8}
          >
            <Volume2 size={13} color="#047857" style={{ marginRight: 4 }} />
            <Text style={styles.btnVoiceText}>Replay Voice</Text>
          </TouchableOpacity>
        )}

        {/* Razorpay Payment Link Button */}
        {sale.razorpay_payment_link_url && (
          <TouchableOpacity
            style={styles.btnRzp}
            onPress={handleOpenRzpLink}
            activeOpacity={0.8}
          >
            <ExternalLink size={13} color={colors.primary} style={{ marginRight: 5 }} />
            <Text style={styles.btnRzpText}>Pay Link</Text>
          </TouchableOpacity>
        )}

        {/* Copy Payment Link */}
        {sale.razorpay_payment_link_url && (
          <TouchableOpacity
            style={styles.btnCopy}
            onPress={handleCopyRzpLink}
            activeOpacity={0.8}
          >
            {copiedLink ? (
              <>
                <Check size={13} color="#047857" style={{ marginRight: 4 }} />
                <Text style={[styles.btnCopyText, { color: '#047857' }]}>Copied!</Text>
              </>
            ) : (
              <>
                <Copy size={13} color={colors.textSecondary} style={{ marginRight: 4 }} />
                <Text style={styles.btnCopyText}>Copy Link</Text>
              </>
            )}
          </TouchableOpacity>
        )}

        {/* Simulate Settlement Button (Available when not fully paid) */}
        {!isPaid && (
          <TouchableOpacity
            style={styles.btnSim}
            onPress={() => onSimulatePayment(sale)}
            activeOpacity={0.8}
          >
            <Zap size={13} color="#ffffff" style={{ marginRight: 5 }} />
            <Text style={styles.btnSimText}>Simulate Settlement</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  cardPaid: {
    borderColor: 'rgba(16, 185, 129, 0.3)',
    backgroundColor: '#FAFCFB',
  },
  cardPartial: {
    borderColor: 'rgba(245, 158, 11, 0.3)',
    backgroundColor: '#FFFDF9',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    flexWrap: 'wrap',
    gap: 8,
  },
  topLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  refBadge: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  refText: {
    fontSize: 11,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: '#334155',
  },
  timeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeText: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '500',
  },
  badgePaid: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ECFDF5',
    borderColor: '#A7F3D0',
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgePaidText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#047857',
    letterSpacing: 0.3,
  },
  badgePartial: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFBEB',
    borderColor: '#FDE68A',
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgePartialText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#B45309',
    letterSpacing: 0.3,
  },
  badgePending: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderColor: '#FECDD3',
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgePendingText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#B91C1C',
    letterSpacing: 0.3,
  },
  orderInfoSection: {
    marginBottom: 12,
  },
  titleRow: {
    marginBottom: 6,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0F172A',
    lineHeight: 20,
  },
  tagsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  customerTag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(79, 70, 229, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(79, 70, 229, 0.2)',
  },
  customerText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.primary,
  },
  voiceNoteTag: {
    backgroundColor: '#F8FAFC',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    maxWidth: 260,
  },
  voiceNoteText: {
    fontSize: 11,
    color: '#64748B',
    fontStyle: 'italic',
  },
  itemPillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
  },
  itemPill: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  itemPillText: {
    fontSize: 11,
    color: '#334155',
  },
  financialRow: {
    flexDirection: 'row',
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 8,
    justifyContent: 'space-around',
    alignItems: 'center',
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  finCol: {
    flex: 1,
    alignItems: 'center',
  },
  finDivider: {
    width: 1,
    height: 28,
    backgroundColor: '#E2E8F0',
  },
  finLabel: {
    fontSize: 9,
    color: '#64748B',
    marginBottom: 4,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  finValueTotal: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0F172A',
  },
  finValueSettled: {
    fontSize: 14,
    fontWeight: '800',
    color: '#059669',
  },
  finValueDue: {
    fontSize: 14,
    fontWeight: '800',
    color: '#DC2626',
  },
  finValueZero: {
    fontSize: 14,
    fontWeight: '700',
    color: '#94A3B8',
  },
  expandableWrap: {
    marginBottom: 12,
  },
  expandToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  expandToggleText: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '600',
  },
  receiptTable: {
    marginTop: 8,
    backgroundColor: '#F8FAFC',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  tableHeader: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
    paddingBottom: 6,
    marginBottom: 6,
  },
  thText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748B',
    textTransform: 'uppercase',
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(226, 232, 240, 0.6)',
  },
  tdText: {
    fontSize: 11,
    color: '#334155',
  },
  tdName: {
    fontWeight: '600',
    color: '#0F172A',
    textTransform: 'capitalize',
  },
  tdSubtotal: {
    fontWeight: '700',
    color: '#0F172A',
  },
  tableFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingTop: 8,
    marginTop: 4,
    gap: 8,
  },
  tfLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
  },
  tfValue: {
    fontSize: 12,
    fontWeight: '800',
    color: '#0F172A',
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
  },
  btnVoiceReplay: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  btnVoiceText: {
    fontSize: 11,
    color: '#047857',
    fontWeight: '700',
  },
  btnRzp: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(79, 70, 229, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(79, 70, 229, 0.25)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  btnRzpText: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '700',
  },
  btnCopy: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  btnCopyText: {
    fontSize: 11,
    color: '#475569',
    fontWeight: '600',
  },
  btnSim: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
    elevation: 2,
  },
  btnSimText: {
    fontSize: 11,
    color: '#FFFFFF',
    fontWeight: '700',
  },
});
