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
              <Zap size={20} color="#f59e0b" style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Simulate Customer Payment</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <X size={18} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <Text style={styles.modalSubtitle}>
            Simulate payment arrival to verify automatic reconciliation and voice status checks.
          </Text>

          {/* Form Fields */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Sale ID</Text>
            <TextInput
              style={[styles.input, styles.inputReadOnly]}
              value={sale.id}
              editable={false}
            />
          </View>

          <View style={styles.formGroup}>
            <Text style={styles.label}>Sold Products</Text>
            <TextInput
              style={[styles.input, styles.inputReadOnly]}
              value={itemsSummary}
              editable={false}
            />
          </View>

          <View style={styles.formRow}>
            <View style={[styles.formGroup, { flex: 1 }]}>
              <Text style={styles.label}>Expected</Text>
              <TextInput
                style={[styles.input, styles.inputReadOnly]}
                value={`₹${sale.total_amount.toFixed(2)}`}
                editable={false}
              />
            </View>
            <View style={[styles.formGroup, { flex: 1 }]}>
              <Text style={styles.label}>Payment Amount (₹)</Text>
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
              <Text style={styles.quickBtnText}>Pay Full (100%)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={handlePayPartial}>
              <Text style={styles.quickBtnText}>Pay Partial (50%)</Text>
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
              <Text style={styles.submitBtnText}>Process Test Payment</Text>
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
    padding: 20,
  },
  modalCard: {
    width: '100%',
    maxWidth: 500,
    backgroundColor: '#121826',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 24,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  titleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  closeBtn: {
    padding: 6,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  modalSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginBottom: 20,
  },
  formGroup: {
    marginBottom: 14,
  },
  formRow: {
    flexDirection: 'row',
    gap: 12,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#0a0e17',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
  },
  inputReadOnly: {
    opacity: 0.7,
  },
  inputActive: {
    borderColor: colors.primary,
  },
  quickBtnRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 20,
    marginTop: 4,
  },
  quickBtn: {
    flex: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  quickBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#a5b4fc',
  },
  submitBtn: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
});
