import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { Zap, X } from 'lucide-react-native';
import { colors } from '../theme/colors';

export default function PaymentSimModal({ visible, sale, onClose, onSubmit, isSubmitting }) {
  const [amountInput, setAmountInput] = useState('');

  useEffect(() => {
    if (sale) {
      setAmountInput(sale.outstanding_amount ? sale.outstanding_amount.toString() : '0');
    }
  }, [sale]);

  if (!sale) return null;

  const itemsSummary = (sale.items && sale.items.length > 0)
    ? sale.items.map(i => `${i.quantity}x ${i.product_name}`).join(', ')
    : (sale.raw_voice_transcript || 'Order items');

  const handlePayFull = () => {
    setAmountInput(sale.outstanding_amount.toString());
  };

  const handlePayPartial = () => {
    const half = Math.round((sale.outstanding_amount / 2) * 100) / 100;
    setAmountInput(half.toString());
  };

  const handleSubmitPayment = () => {
    const amt = parseFloat(amountInput);
    if (isNaN(amt) || amt <= 0) {
      alert('Please enter a valid payment amount');
      return;
    }
    onSubmit(sale.id, amt);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.modalHeader}>
            <View style={styles.titleWrap}>
              <Zap size={16} color={colors.primary} style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Simulate Payment Settlement</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <X size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <Text style={styles.modalSubtitle}>
            Simulate customer payment arrival to trigger automatic ledger reconciliation and voice soundbox confirmation.
          </Text>

          {/* Form Fields */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Transaction ID</Text>
            <TextInput
              style={[styles.input, styles.inputReadOnly]}
              value={sale.id}
              editable={false}
            />
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.label}>Purchased Items</Text>
            <TextInput
              style={[styles.input, styles.inputReadOnly]}
              value={itemsSummary}
              editable={false}
            />
          </View>

          <View style={styles.formRow}>
            <View style={[styles.formGroup, { flex: 1 }]}>
              <Text style={styles.label}>Total Payable</Text>
              <TextInput
                style={[styles.input, styles.inputReadOnly]}
                value={`₹${sale.total_amount.toFixed(2)}`}
                editable={false}
              />
            </View>
            <View style={[styles.formGroup, { flex: 1 }]}>
              <Text style={styles.label}>Settlement Amount (₹)</Text>
              <TextInput
                style={[styles.input, styles.inputActive]}
                value={amountInput}
                onChangeText={setAmountInput}
                keyboardType="numeric"
              />
            </View>
          </View>

          {/* Quick Buttons */}
          <View style={styles.quickBtnRow}>
            <TouchableOpacity style={styles.quickBtn} onPress={handlePayFull}>
              <Text style={styles.quickBtnText}>Full Settlement (100%)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={handlePayPartial}>
              <Text style={styles.quickBtnText}>Partial Settlement (50%)</Text>
            </TouchableOpacity>
          </View>

          {/* Submit Button */}
          <TouchableOpacity
            style={[styles.submitBtn, isSubmitting && styles.submitBtnDisabled]}
            onPress={handleSubmitPayment}
            disabled={isSubmitting}
            activeOpacity={0.8}
          >
            {isSubmitting ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.submitBtnText}>Execute Settlement</Text>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 480,
    backgroundColor: colors.bgCard,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 20,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  closeBtn: {
    padding: 4,
  },
  modalSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 16,
    lineHeight: 16,
  },
  formGroup: {
    marginBottom: 12,
  },
  formRow: {
    flexDirection: 'row',
    gap: 10,
  },
  label: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
    marginBottom: 4,
  },
  input: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: colors.textPrimary,
    fontSize: 13,
  },
  inputReadOnly: {
    opacity: 0.7,
  },
  inputActive: {
    borderColor: colors.primary,
  },
  quickBtnRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
    marginTop: 2,
  },
  quickBtn: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingVertical: 8,
    alignItems: 'center',
  },
  quickBtnText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.primary,
  },
  submitBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingVertical: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#ffffff',
  },
});
