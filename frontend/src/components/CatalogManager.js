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
  Platform,
} from 'react-native';
import { colors } from '../theme/colors';
import { apiService } from '../services/apiService';

const PRESET_UNITS = ['kg', 'gram', 'piece', 'packet', 'strip', 'plate', 'glass', 'bottle', 'litre', 'box', 'dozen', 'meter'];

const DOMAIN_TEMPLATES = {
  '🍎 Fruits & Veg': [
    { key: 'Origin', value: 'Local / Farm Fresh' },
    { key: 'Organic', value: 'Yes' },
    { key: 'Shelf Life', value: '3-4 Days' },
  ],
  '💊 Pharmacy': [
    { key: 'Dosage', value: '500mg' },
    { key: 'Manufacturer', value: 'Cipla' },
    { key: 'Expiry Date', value: '12/2027' },
    { key: 'Rx Required', value: 'No' },
  ],
  '🍽️ Cafe / Restaurant': [
    { key: 'Dietary', value: 'Vegetarian' },
    { key: 'Spice Level', value: 'Medium' },
    { key: 'Portion', value: 'Full Plate' },
  ],
  '👕 Apparel': [
    { key: 'Size', value: 'L / 42' },
    { key: 'Color', value: 'Navy Blue' },
    { key: 'Fabric', value: '100% Cotton' },
  ],
  '🔩 Hardware': [
    { key: 'Material', value: 'Stainless Steel' },
    { key: 'Dimensions', value: '12mm x 50mm' },
  ],
};

export default function CatalogManager({ onCatalogUpdated }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  // Modal State
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null); // null = add, object = edit
  const [formName, setFormName] = useState('');
  const [formPrice, setFormPrice] = useState('');
  const [formCategory, setFormCategory] = useState('General');
  const [formUnit, setFormUnit] = useState('piece');
  const [formDescription, setFormDescription] = useState('');
  const [formAttributes, setFormAttributes] = useState([]); // [{ key: '', value: '' }]
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const loadProducts = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await apiService.getCatalogProducts(null, searchQuery);
      setProducts(data || []);
    } catch (e) {
      console.warn('Failed to load catalog:', e.message);
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const openAddModal = () => {
    setEditingProduct(null);
    setFormName('');
    setFormPrice('');
    setFormCategory('General');
    setFormUnit('piece');
    setFormDescription('');
    setFormAttributes([]);
    setFormError('');
    setModalVisible(true);
  };

  const openEditModal = (product) => {
    setEditingProduct(product);
    setFormName(product.name || '');
    setFormPrice(String(product.price || ''));
    setFormCategory(product.category || 'General');
    setFormUnit(product.unit || 'piece');
    setFormDescription(product.description || '');

    // Convert attributes dict to array
    const rawAttrs = product.attributes || {};
    const attrsArr = Object.entries(rawAttrs).map(([k, v]) => ({ key: k, value: String(v) }));
    setFormAttributes(attrsArr);
    setFormError('');
    setModalVisible(true);
  };

  const handleApplyTemplate = (templateName) => {
    const templateFields = DOMAIN_TEMPLATES[templateName] || [];
    setFormAttributes((prev) => {
      const existingKeys = new Set(prev.map((a) => a.key.toLowerCase()));
      const newAdditions = templateFields.filter((t) => !existingKeys.has(t.key.toLowerCase()));
      return [...prev, ...newAdditions];
    });
  };

  const handleAddAttributeField = () => {
    setFormAttributes((prev) => [...prev, { key: '', value: '' }]);
  };

  const handleUpdateAttribute = (index, field, text) => {
    setFormAttributes((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: text };
      return updated;
    });
  };

  const handleRemoveAttribute = (index) => {
    setFormAttributes((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSaveProduct = async () => {
    if (!formName.trim()) {
      setFormError('Item name is required');
      return;
    }
    const parsedPrice = parseFloat(formPrice);
    if (isNaN(parsedPrice) || parsedPrice < 0) {
      setFormError('Please enter a valid price');
      return;
    }

    // Convert attributes array to object
    const attrsObj = {};
    formAttributes.forEach((attr) => {
      if (attr.key.trim()) {
        attrsObj[attr.key.trim()] = attr.value.trim();
      }
    });

    setIsSubmitting(true);
    setFormError('');
    try {
      const payload = {
        name: formName.trim(),
        price: parsedPrice,
        category: formCategory.trim() || 'General',
        unit: formUnit.trim() || undefined,
        description: formDescription.trim() || undefined,
        attributes: attrsObj,
      };

      if (editingProduct) {
        await apiService.updateCatalogProduct(editingProduct.id, payload);
      } else {
        await apiService.addCatalogProduct(payload);
      }

      setModalVisible(false);
      await loadProducts();
      if (onCatalogUpdated) onCatalogUpdated();
    } catch (e) {
      setFormError(e.message || 'Failed to save product');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProduct = async (productId) => {
    const isOk = Platform.OS === 'web' && typeof window !== 'undefined'
      ? window.confirm('Are you sure you want to deactivate this item?')
      : true;
    if (isOk) {
      try {
        await apiService.deleteCatalogProduct(productId);
        await loadProducts();
        if (onCatalogUpdated) onCatalogUpdated();
      } catch (e) {
        alert(`Delete failed: ${e.message}`);
      }
    }
  };

  const categories = ['ALL', ...Array.from(new Set(products.map((p) => p.category || 'General')))];

  const filteredProducts = products.filter((p) => {
    if (selectedCategory !== 'ALL' && (p.category || 'General') !== selectedCategory) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (p.name || '').toLowerCase().includes(q);
      const matchCat = (p.category || '').toLowerCase().includes(q);
      const matchDesc = (p.description || '').toLowerCase().includes(q);
      return matchName || matchCat || matchDesc;
    }
    return true;
  });

  return (
    <View style={styles.container}>
      {/* 1. Header Bar */}
      <View style={[styles.headerRow, isMobile && styles.headerRowMobile]}>
        <View style={{ flex: 1 }}>
          <View style={styles.badgeHub}>
            <Text style={styles.badgeHubText}>📦 Open-Ended Schema Catalog</Text>
          </View>
          <Text style={styles.title}>Menu & Catalog Management</Text>
          <Text style={styles.subtitle}>
            Manage any products or services with dynamic specifications (Fruits, Pharmacy, Food, Apparel, Hardware).
          </Text>
        </View>

        <TouchableOpacity style={styles.addItemBtn} onPress={openAddModal} activeOpacity={0.8}>
          <Text style={styles.addItemBtnText}>➕ Add Item / Menu</Text>
        </TouchableOpacity>
      </View>

      {/* 2. Search & Filter Bar */}
      <View style={styles.filterCard}>
        <View style={styles.searchInputWrapper}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            style={styles.searchInput}
            placeholder="Search items by name, category, or description..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearBtn}>
              <Text style={styles.clearBtnText}>✕</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.catScroll}>
          {categories.map((cat) => {
            const count = cat === 'ALL' ? products.length : products.filter((p) => (p.category || 'General') === cat).length;
            const isActive = selectedCategory === cat;
            return (
              <TouchableOpacity
                key={cat}
                style={[styles.catChip, isActive && styles.catChipActive]}
                onPress={() => setSelectedCategory(cat)}
              >
                <Text style={[styles.catChipText, isActive && styles.catChipTextActive]}>
                  {cat} ({count})
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* 3. Products List / Grid */}
      {isLoading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading store items...</Text>
        </View>
      ) : filteredProducts.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyEmoji}>📦</Text>
          <Text style={styles.emptyTitle}>No items found in catalog</Text>
          <Text style={styles.emptySub}>
            Click "➕ Add Item / Menu" or speak to the voice assistant to list items.
          </Text>
        </View>
      ) : (
        <View style={[styles.productGrid, isMobile && styles.productGridMobile]}>
          {filteredProducts.map((p) => {
            const attrs = p.attributes || {};
            const attrEntries = Object.entries(attrs);

            return (
              <View key={p.id} style={styles.productCard}>
                <View style={styles.cardHeader}>
                  <View style={{ flex: 1 }}>
                    <View style={styles.categoryRow}>
                      <View style={styles.catPill}>
                        <Text style={styles.catPillText}>{p.category || 'General'}</Text>
                      </View>
                      {p.unit ? (
                        <View style={styles.unitPill}>
                          <Text style={styles.unitPillText}>per {p.unit}</Text>
                        </View>
                      ) : null}
                    </View>
                    <Text style={styles.prodName} numberOfLines={2}>
                      {p.name.charAt(0).toUpperCase() + p.name.slice(1)}
                    </Text>
                  </View>

                  <View style={styles.priceContainer}>
                    <Text style={styles.priceText}>₹{p.price.toFixed(2)}</Text>
                  </View>
                </View>

                {p.description ? (
                  <Text style={styles.descText} numberOfLines={2}>
                    {p.description}
                  </Text>
                ) : null}

                {/* Dynamic Attributes Tags */}
                {attrEntries.length > 0 ? (
                  <View style={styles.attrsContainer}>
                    {attrEntries.map(([k, v]) => (
                      <View key={k} style={styles.attrTag}>
                        <Text style={styles.attrTagKey}>{k}: </Text>
                        <Text style={styles.attrTagVal}>{String(v)}</Text>
                      </View>
                    ))}
                  </View>
                ) : null}

                {/* Actions Row */}
                <View style={styles.cardFooter}>
                  <TouchableOpacity style={styles.editBtn} onPress={() => openEditModal(p)}>
                    <Text style={styles.editBtnText}>✏️ Edit</Text>
                  </TouchableOpacity>

                  <TouchableOpacity style={styles.delBtn} onPress={() => handleDeleteProduct(p.id)}>
                    <Text style={styles.delBtnText}>🗑️ Deactivate</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}
        </View>
      )}

      {/* 4. Add / Edit Item Modal with Dynamic Schema */}
      <Modal visible={modalVisible} transparent animationType="fade" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, isMobile && styles.modalCardMobile]}>
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>{editingProduct ? 'Edit Catalog Item' : 'Add New Item / Menu'}</Text>
                <Text style={styles.modalSub}>Supports any business domain with dynamic attributes</Text>
              </View>
              <TouchableOpacity onPress={() => setModalVisible(false)} style={styles.closeBtn}>
                <Text style={styles.closeBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalScroll}>
              {formError ? (
                <View style={styles.errorBox}>
                  <Text style={styles.errorText}>⚠️ {formError}</Text>
                </View>
              ) : null}

              {/* Item Name */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Item Name *</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="e.g. Shimla Apple, Paracetamol 650, Butter Chicken, A4 Sheet"
                  placeholderTextColor={colors.textMuted}
                  value={formName}
                  onChangeText={setFormName}
                />
              </View>

              {/* Price & Unit Row */}
              <View style={styles.rowTwo}>
                <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                  <Text style={styles.inputLabel}>Price (₹) *</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="0.00"
                    placeholderTextColor={colors.textMuted}
                    value={formPrice}
                    onChangeText={setFormPrice}
                    keyboardType="numeric"
                  />
                </View>

                <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                  <Text style={styles.inputLabel}>Unit of Measure</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="e.g. kg, plate, piece, strip"
                    placeholderTextColor={colors.textMuted}
                    value={formUnit}
                    onChangeText={setFormUnit}
                  />
                </View>
              </View>

              {/* Quick Unit Chips */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.presetScroll}>
                {PRESET_UNITS.map((u) => (
                  <TouchableOpacity
                    key={u}
                    style={[styles.presetChip, formUnit === u && styles.presetChipActive]}
                    onPress={() => setFormUnit(u)}
                  >
                    <Text style={[styles.presetChipText, formUnit === u && styles.presetChipTextActive]}>{u}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>

              {/* Category */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Category</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="e.g. Fruits, Pharmacy, Bakery, Snacks, Hardware, Apparel"
                  placeholderTextColor={colors.textMuted}
                  value={formCategory}
                  onChangeText={setFormCategory}
                />
              </View>

              {/* Description */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Description (Optional)</Text>
                <TextInput
                  style={[styles.textInput, { height: 60 }]}
                  placeholder="Additional details about the product or item..."
                  placeholderTextColor={colors.textMuted}
                  value={formDescription}
                  onChangeText={setFormDescription}
                  multiline
                />
              </View>

              {/* ── Dynamic Attributes Builder (Open Schema) ── */}
              <View style={styles.attrsSection}>
                <View style={styles.attrsSectionHeader}>
                  <View>
                    <Text style={styles.attrsTitle}>Dynamic Attributes & Specs</Text>
                    <Text style={styles.attrsSub}>Custom parameters for your store type</Text>
                  </View>
                  <TouchableOpacity style={styles.addAttrBtn} onPress={handleAddAttributeField}>
                    <Text style={styles.addAttrBtnText}>➕ Add Field</Text>
                  </TouchableOpacity>
                </View>

                {/* Domain Quick Templates */}
                <View style={styles.templatePresets}>
                  <Text style={styles.templatePresetsLabel}>Quick Templates:</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
                    {Object.keys(DOMAIN_TEMPLATES).map((tName) => (
                      <TouchableOpacity
                        key={tName}
                        style={styles.templateBtn}
                        onPress={() => handleApplyTemplate(tName)}
                      >
                        <Text style={styles.templateBtnText}>{tName}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>

                {/* Attributes Key-Value Rows */}
                {formAttributes.map((attr, idx) => (
                  <View key={idx} style={styles.attrInputRow}>
                    <TextInput
                      style={[styles.attrInput, { flex: 1, marginRight: 6 }]}
                      placeholder="Key (e.g. Dosage, Origin, Size)"
                      placeholderTextColor={colors.textMuted}
                      value={attr.key}
                      onChangeText={(val) => handleUpdateAttribute(idx, 'key', val)}
                    />
                    <TextInput
                      style={[styles.attrInput, { flex: 1.2, marginRight: 6 }]}
                      placeholder="Value (e.g. 500mg, Kashmir, XL)"
                      placeholderTextColor={colors.textMuted}
                      value={attr.value}
                      onChangeText={(val) => handleUpdateAttribute(idx, 'value', val)}
                    />
                    <TouchableOpacity style={styles.removeAttrBtn} onPress={() => handleRemoveAttribute(idx)}>
                      <Text style={styles.removeAttrBtnText}>✕</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            </ScrollView>

            {/* Modal Actions Footer */}
            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.cancelModalBtn}
                onPress={() => setModalVisible(false)}
                disabled={isSubmitting}
              >
                <Text style={styles.cancelModalBtnText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.saveModalBtn}
                onPress={handleSaveProduct}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Text style={styles.saveModalBtnText}>{editingProduct ? 'Update Item' : 'Save Item'}</Text>
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
    backgroundColor: 'rgba(6, 182, 212, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(6, 182, 212, 0.3)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: 'flex-start',
    marginBottom: 6,
  },
  badgeHubText: {
    color: colors.accentCyan,
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
  addItemBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },
  addItemBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 14,
  },

  // Filters Card
  filterCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
    marginBottom: 20,
  },
  searchInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    marginBottom: 10,
  },
  searchIcon: {
    fontSize: 15,
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    height: 42,
    color: colors.textPrimary,
    fontSize: 13,
  },
  clearBtn: {
    padding: 6,
  },
  clearBtnText: {
    color: colors.textMuted,
    fontSize: 13,
  },
  catScroll: {
    flexDirection: 'row',
  },
  catChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 18,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  catChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  catChipText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  catChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },

  // Products Grid
  productGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
  },
  productGridMobile: {
    flexDirection: 'column',
  },
  productCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 16,
    flex: 1,
    minWidth: 280,
    maxWidth: '100%',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  categoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  catPill: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  catPillText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  unitPill: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  unitPillText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '600',
  },
  prodName: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  priceContainer: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  priceText: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.accentEmerald,
  },
  descText: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 10,
    lineHeight: 16,
  },

  // Dynamic Attributes Tags
  attrsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: 10,
    padding: 8,
  },
  attrTag: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  attrTagKey: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '700',
  },
  attrTagVal: {
    fontSize: 11,
    color: colors.textPrimary,
    fontWeight: '600',
  },

  // Card Footer
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
    paddingTop: 10,
  },
  editBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.3)',
  },
  editBtnText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  delBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
  },
  delBtnText: {
    color: colors.textMuted,
    fontSize: 12,
  },

  // Loading & Empty States
  loadingBox: {
    padding: 60,
    alignItems: 'center',
  },
  loadingText: {
    color: colors.textSecondary,
    marginTop: 12,
    fontSize: 14,
  },
  emptyBox: {
    padding: 40,
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  emptyEmoji: {
    fontSize: 40,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySub: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    backgroundColor: '#121826',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 20,
    width: '100%',
    maxWidth: 560,
    maxHeight: '90%',
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
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  modalSub: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },
  closeBtn: {
    padding: 4,
  },
  closeBtnText: {
    color: colors.textMuted,
    fontSize: 18,
  },
  modalScroll: {
    maxHeight: 460,
  },
  errorBox: {
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    borderColor: 'rgba(244, 63, 94, 0.3)',
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    marginBottom: 12,
  },
  errorText: {
    color: colors.accentRose,
    fontSize: 12,
    fontWeight: '600',
  },
  inputGroup: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 6,
  },
  textInput: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 42,
    color: colors.textPrimary,
    fontSize: 13,
  },
  rowTwo: {
    flexDirection: 'row',
  },
  presetScroll: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  presetChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    marginRight: 6,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  presetChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  presetChipText: {
    color: colors.textMuted,
    fontSize: 11,
  },
  presetChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },

  // Dynamic Attributes Section
  attrsSection: {
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 12,
    marginBottom: 16,
  },
  attrsSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  attrsTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  attrsSub: {
    fontSize: 11,
    color: colors.textMuted,
  },
  addAttrBtn: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.3)',
  },
  addAttrBtnText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '700',
  },
  templatePresets: {
    marginBottom: 10,
  },
  templatePresetsLabel: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
  },
  templateBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginRight: 6,
  },
  templateBtnText: {
    color: colors.textSecondary,
    fontSize: 11,
  },
  attrInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  attrInput: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    height: 38,
    color: colors.textPrimary,
    fontSize: 12,
  },
  removeAttrBtn: {
    padding: 8,
  },
  removeAttrBtnText: {
    color: colors.accentRose,
    fontSize: 14,
    fontWeight: '800',
  },

  // Modal Footer
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
    paddingTop: 12,
  },
  cancelModalBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  cancelModalBtnText: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  saveModalBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    minWidth: 110,
    alignItems: 'center',
  },
  saveModalBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '800',
  },
});
