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
import {
  Package,
  Plus,
  Search,
  Edit3,
  Trash2,
  Tag,
  SlidersHorizontal,
  PackageOpen,
  X,
  AlertCircle,
  Layers,
} from 'lucide-react-native';
import { colors } from '../theme/colors';
import { apiService } from '../services/apiService';
import { voiceService } from '../services/voiceService';

const PRESET_UNITS = ['kg', 'gram', 'piece', 'packet', 'strip', 'plate', 'glass', 'bottle', 'litre', 'box', 'dozen', 'meter'];

const DOMAIN_TEMPLATES = {
  'Produce & Grocery': [
    { key: 'Origin', value: 'Local / Farm Fresh' },
    { key: 'Organic', value: 'Yes' },
    { key: 'Shelf Life', value: '3-4 Days' },
  ],
  'Pharmaceuticals': [
    { key: 'Dosage', value: '500mg' },
    { key: 'Manufacturer', value: 'Cipla' },
    { key: 'Expiry Date', value: '12/2027' },
    { key: 'Rx Required', value: 'No' },
  ],
  'Food & Dining': [
    { key: 'Dietary', value: 'Vegetarian' },
    { key: 'Spice Level', value: 'Medium' },
    { key: 'Portion', value: 'Full Plate' },
  ],
  'Apparel & Fashion': [
    { key: 'Size', value: 'L / 42' },
    { key: 'Color', value: 'Navy Blue' },
    { key: 'Fabric', value: '100% Cotton' },
  ],
  'Hardware & Electrical': [
    { key: 'Material', value: 'Stainless Steel' },
    { key: 'Dimensions', value: '12mm x 50mm' },
  ],
};

const CATALOG_VOICE_PROMPTS = [
  { label: '🍽️ Menu dikhao', prompt: 'Menu dikhao' },
  { label: '➕ Chai add karo ₹20', prompt: 'Menu mein chai add karo 20 rupaye' },
  { label: '🔍 Coffee ka price?', prompt: 'Coffee ka price kya hai' },
  { label: '📋 Catalog list', prompt: 'Catalog batao kitne items hain' },
];

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

  // Business type & voice assistant state
  const [businessTypes, setBusinessTypes] = useState([]);
  const [selectedBusinessType, setSelectedBusinessType] = useState('Kirana & Retail');
  const [businessPresets, setBusinessPresets] = useState({});
  const [isSettingBusinessType, setIsSettingBusinessType] = useState(false);
  const [catalogVoiceText, setCatalogVoiceText] = useState('');
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);
  const [voiceResponse, setVoiceResponse] = useState(null);
  const [isRecording, setIsRecording] = useState(false);

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

  useEffect(() => {
    const loadBusinessContext = async () => {
      try {
        const [typesData, merchant] = await Promise.all([
          apiService.getBusinessTypes(),
          apiService.getMerchant(),
        ]);
        setBusinessTypes(typesData.types || []);
        setBusinessPresets(typesData.presets || {});
        if (merchant?.business_type) {
          setSelectedBusinessType(merchant.business_type);
        }
      } catch (e) {
        console.warn('Business context load notice:', e.message);
      }
    };
    loadBusinessContext();
  }, []);

  useEffect(() => {
    voiceService.initWebSpeech(
      (transcript) => {
        setCatalogVoiceText(transcript);
        handleCatalogVoice(transcript);
      },
      () => setIsRecording(true),
      () => setIsRecording(false),
      () => setIsRecording(false)
    );
  }, []);

  const handleBusinessTypeChange = async (typeId) => {
    setIsSettingBusinessType(true);
    try {
      const shouldSeed = products.length === 0;
      await apiService.setBusinessType(typeId, shouldSeed);
      setSelectedBusinessType(typeId);
      const preset = businessPresets[typeId];
      if (preset?.default_categories?.length && formCategory === 'General') {
        setFormCategory(preset.default_categories[0]);
      }
      await loadProducts();
      if (onCatalogUpdated) onCatalogUpdated();
    } catch (e) {
      alert(`Business type update failed: ${e.message}`);
    } finally {
      setIsSettingBusinessType(false);
    }
  };

  const handleCatalogVoice = async (overrideText = null) => {
    const query = (overrideText || catalogVoiceText).trim();
    if (!query || isVoiceProcessing) return;

    setIsVoiceProcessing(true);
    setVoiceResponse({ reply: 'Catalog assistant is processing...', action: 'Processing' });

    try {
      const data = await apiService.processVoiceCommand(query, 'catalog');
      setVoiceResponse({
        reply: data.agent_reply || 'Done.',
        action: data.action_taken || 'Completed',
      });
      if (data.audio_base64 || data.agent_reply) {
        voiceService.playTTSAudio(data.audio_base64, data.agent_reply);
      }
      setCatalogVoiceText('');
      await loadProducts();
      if (onCatalogUpdated) onCatalogUpdated();
    } catch (e) {
      setVoiceResponse({ reply: `Error: ${e.message}`, action: 'Failed' });
    } finally {
      setIsVoiceProcessing(false);
    }
  };

  const toggleVoiceRecording = () => {
    if (isRecording) {
      voiceService.stopListening();
      setIsRecording(false);
    } else if (Platform.OS === 'web') {
      voiceService.startListening();
    }
  };

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
          <Text style={styles.title}>Product Catalog & Inventory</Text>
          <Text style={styles.subtitle}>
            Dynamic multi-domain inventory with custom attributes for grocery, pharmacy, food, fashion, and hardware.
          </Text>
        </View>

        <TouchableOpacity style={styles.addItemBtn} onPress={openAddModal} activeOpacity={0.8}>
          <Plus size={15} color="#ffffff" style={{ marginRight: 6 }} />
          <Text style={styles.addItemBtnText}>Add Product</Text>
        </TouchableOpacity>
      </View>

      {/* Business Type Selector */}
      <View style={styles.businessTypeCard}>
        <Text style={styles.businessTypeLabel}>🏪 Store Type (flexible — add any items you want)</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.businessTypeScroll}>
          {(businessTypes.length ? businessTypes : [{ id: 'Kirana & Retail', label: '🏪 Kirana & Retail' }]).map((bt) => {
            const isActive = selectedBusinessType === bt.id;
            return (
              <TouchableOpacity
                key={bt.id}
                style={[styles.businessTypeChip, isActive && styles.businessTypeChipActive]}
                onPress={() => handleBusinessTypeChange(bt.id)}
                disabled={isSettingBusinessType}
              >
                <Text style={[styles.businessTypeChipText, isActive && styles.businessTypeChipTextActive]}>
                  {bt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        {isSettingBusinessType ? (
          <ActivityIndicator size="small" color={colors.primary} style={{ marginTop: 8 }} />
        ) : null}
      </View>

      {/* Voice-Assisted Catalog Panel */}
      <View style={styles.voicePanel}>
        <View style={styles.voicePanelHeader}>
          <Text style={styles.voicePanelTitle}>🎙️ Voice-Assisted Catalog</Text>
          <Text style={styles.voicePanelSub}>
            Add, search, or list items by voice — catalog adapts to your store type
          </Text>
        </View>
        <View style={styles.voiceInputRow}>
          <TouchableOpacity
            style={[styles.voiceMicBtn, isRecording && styles.voiceMicBtnActive]}
            onPress={toggleVoiceRecording}
          >
            <Text style={styles.voiceMicIcon}>{isRecording ? '⏹️' : '🎤'}</Text>
          </TouchableOpacity>
          <TextInput
            style={styles.voiceTextInput}
            placeholder="Bolein: 'Menu mein dosa add karo 80 rupaye' ya 'Menu dikhao'"
            placeholderTextColor={colors.textMuted}
            value={catalogVoiceText}
            onChangeText={setCatalogVoiceText}
            onSubmitEditing={() => handleCatalogVoice()}
          />
          <TouchableOpacity
            style={[styles.voiceSendBtn, (!catalogVoiceText.trim() || isVoiceProcessing) && styles.voiceSendBtnDisabled]}
            onPress={() => handleCatalogVoice()}
            disabled={!catalogVoiceText.trim() || isVoiceProcessing}
          >
            {isVoiceProcessing ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.voiceSendText}>Go</Text>
            )}
          </TouchableOpacity>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.voiceChipsScroll}>
          {CATALOG_VOICE_PROMPTS.map((item, idx) => (
            <TouchableOpacity
              key={idx}
              style={styles.voiceChip}
              onPress={() => {
                setCatalogVoiceText(item.prompt);
                handleCatalogVoice(item.prompt);
              }}
            >
              <Text style={styles.voiceChipText}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        {voiceResponse ? (
          <View style={styles.voiceResponseBox}>
            <Text style={styles.voiceResponseAction}>{voiceResponse.action}</Text>
            <Text style={styles.voiceResponseText}>{voiceResponse.reply}</Text>
          </View>
        ) : null}
      </View>

      {/* 2. Search & Filter Bar */}
      <View style={styles.filterCard}>
        <View style={styles.searchInputWrapper}>
          <Search size={15} color={colors.textMuted} style={{ marginRight: 8 }} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search items by name, category, or description..."
            placeholderTextColor={colors.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearBtn}>
              <Text style={styles.clearBtnText}>Clear</Text>
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
          <Text style={styles.loadingText}>Loading inventory records...</Text>
        </View>
      ) : filteredProducts.length === 0 ? (
        <View style={styles.emptyBox}>
          <PackageOpen size={36} color={colors.textMuted} style={{ marginBottom: 8 }} />
          <Text style={styles.emptyTitle}>No products found</Text>
          <Text style={styles.emptySub}>
            Select your store type above, then add items manually or use voice: &quot;Menu mein chai add karo 20 rupaye&quot;
          </Text>
          <TouchableOpacity style={styles.emptyAddBtn} onPress={openAddModal}>
            <Text style={styles.emptyAddBtnText}>➕ Add First Item</Text>
          </TouchableOpacity>
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
                    <Edit3 size={13} color={colors.primary} style={{ marginRight: 5 }} />
                    <Text style={styles.editBtnText}>Edit</Text>
                  </TouchableOpacity>

                  <TouchableOpacity style={styles.delBtn} onPress={() => handleDeleteProduct(p.id)}>
                    <Trash2 size={13} color={colors.accentRose} style={{ marginRight: 5 }} />
                    <Text style={styles.delBtnText}>Deactivate</Text>
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
                <Text style={styles.modalTitle}>{editingProduct ? 'Edit Catalog Item' : 'New Product Entry'}</Text>
                <Text style={styles.modalSub}>Supports custom specifications for any business domain</Text>
              </View>
              <TouchableOpacity onPress={() => setModalVisible(false)} style={styles.closeBtn}>
                <X size={18} color={colors.textMuted} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalScroll}>
              {formError ? (
                <View style={styles.errorBox}>
                  <AlertCircle size={15} color={colors.accentRose} style={{ marginRight: 8 }} />
                  <Text style={styles.errorText}>{formError}</Text>
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
                  <Text style={styles.inputLabel}>Unit Price (₹) *</Text>
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

              {/* Dynamic Attributes Builder */}
              <View style={styles.attrsSection}>
                <View style={styles.attrsSectionHeader}>
                  <View>
                    <Text style={styles.attrsTitle}>Custom Specification Attributes</Text>
                    <Text style={styles.attrsSub}>Flexible key-value parameters for item specifications</Text>
                  </View>
                  <TouchableOpacity style={styles.addAttrBtn} onPress={handleAddAttributeField}>
                    <Plus size={13} color={colors.primary} style={{ marginRight: 4 }} />
                    <Text style={styles.addAttrBtnText}>Add Attribute</Text>
                  </TouchableOpacity>
                </View>

                {/* Domain Quick Templates */}
                <View style={styles.templatePresets}>
                  <Text style={styles.templatePresetsLabel}>Preset Templates:</Text>
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
                      placeholder="Attribute Key (e.g. Dosage, Size)"
                      placeholderTextColor={colors.textMuted}
                      value={attr.key}
                      onChangeText={(val) => handleUpdateAttribute(idx, 'key', val)}
                    />
                    <TextInput
                      style={[styles.attrInput, { flex: 1.2, marginRight: 6 }]}
                      placeholder="Value (e.g. 500mg, XL)"
                      placeholderTextColor={colors.textMuted}
                      value={attr.value}
                      onChangeText={(val) => handleUpdateAttribute(idx, 'value', val)}
                    />
                    <TouchableOpacity style={styles.removeAttrBtn} onPress={() => handleRemoveAttribute(idx)}>
                      <X size={14} color={colors.textMuted} />
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            </ScrollView>

            {/* Modal Actions Footer */}
            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.btnCancel} onPress={() => setModalVisible(false)}>
                <Text style={styles.btnCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.btnSave}
                onPress={handleSaveProduct}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Text style={styles.btnSaveText}>{editingProduct ? 'Save Changes' : 'Create Product'}</Text>
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
  addItemBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  addItemBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
  filterCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
    marginBottom: 16,
  },
  searchInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 10,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 12,
  },
  clearBtn: {
    padding: 4,
  },
  clearBtnText: {
    color: colors.textMuted,
    fontSize: 11,
  },
  catScroll: {
    flexDirection: 'row',
  },
  catChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginRight: 6,
  },
  catChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  catChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
  },
  catChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  loadingBox: {
    paddingVertical: 40,
    alignItems: 'center',
  },
  loadingText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 8,
  },
  emptyBox: {
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingVertical: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  emptySub: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 400,
    marginBottom: 12,
  },
  emptyAddBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 10,
  },
  emptyAddBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 13,
  },
  businessTypeCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
    marginBottom: 16,
  },
  businessTypeLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: 10,
  },
  businessTypeScroll: {
    flexDirection: 'row',
  },
  businessTypeChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(15, 23, 42, 0.05)',
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  businessTypeChipActive: {
    backgroundColor: 'rgba(6, 182, 212, 0.15)',
    borderColor: colors.accentCyan,
  },
  businessTypeChipText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  businessTypeChipTextActive: {
    color: colors.accentCyan,
    fontWeight: '700',
  },
  voicePanel: {
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.25)',
    padding: 16,
    marginBottom: 16,
  },
  voicePanelHeader: {
    marginBottom: 12,
  },
  voicePanelTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  voicePanelSub: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },
  voiceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  voiceMicBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  voiceMicBtnActive: {
    backgroundColor: colors.accentRose,
  },
  voiceMicIcon: {
    fontSize: 18,
  },
  voiceTextInput: {
    flex: 1,
    height: 42,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 10,
    paddingHorizontal: 12,
    color: colors.textPrimary,
    fontSize: 13,
  },
  voiceSendBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    height: 42,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  voiceSendBtnDisabled: {
    opacity: 0.5,
  },
  voiceSendText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 13,
  },
  voiceChipsScroll: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  voiceChip: {
    backgroundColor: 'rgba(15, 23, 42, 0.06)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  voiceChipText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  voiceResponseBox: {
    backgroundColor: 'rgba(0, 0, 0, 0.25)',
    borderRadius: 10,
    padding: 10,
    marginTop: 6,
  },
  voiceResponseAction: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.primary,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  voiceResponseText: {
    fontSize: 13,
    color: colors.textPrimary,
    lineHeight: 18,
  },
  productGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  productGridMobile: {
    flexDirection: 'column',
  },
  productCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
    flex: 1,
    minWidth: 260,
    maxWidth: '49%',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  categoryRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 4,
  },
  catPill: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  catPillText: {
    fontSize: 10,
    color: colors.primary,
    fontWeight: '600',
  },
  unitPill: {
    backgroundColor: 'rgba(15, 23, 42, 0.05)',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  unitPillText: {
    fontSize: 10,
    color: colors.textMuted,
  },
  prodName: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  priceContainer: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.25)',
  },
  priceText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#34d399',
  },
  descText: {
    fontSize: 11,
    color: colors.textSecondary,
    marginBottom: 8,
    lineHeight: 15,
  },
  attrsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginBottom: 10,
  },
  attrTag: {
    flexDirection: 'row',
    backgroundColor: '#F8FAFC',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  attrTagKey: {
    fontSize: 10,
    color: colors.textMuted,
    fontWeight: '600',
  },
  attrTagVal: {
    fontSize: 10,
    color: colors.textSecondary,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
  },
  editBtnText: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '600',
  },
  delBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
  },
  delBtnText: {
    fontSize: 11,
    color: colors.accentRose,
    fontWeight: '600',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 520,
    backgroundColor: colors.bgCard,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderColor,
    maxHeight: '90vh',
  },
  modalCardMobile: {
    maxWidth: '100%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 18,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  modalSub: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  closeBtn: {
    padding: 4,
  },
  modalScroll: {
    padding: 18,
    maxHeight: 480,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
    borderRadius: 6,
    padding: 8,
    marginBottom: 12,
  },
  errorText: {
    color: '#fb7185',
    fontSize: 12,
  },
  inputGroup: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: colors.textPrimary,
    fontSize: 12,
  },
  rowTwo: {
    flexDirection: 'row',
  },
  presetScroll: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  presetChip: {
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    marginRight: 4,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  presetChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  presetChipText: {
    fontSize: 10,
    color: colors.textMuted,
  },
  presetChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  attrsSection: {
    marginTop: 10,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  attrsSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  attrsTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  attrsSub: {
    fontSize: 10,
    color: colors.textMuted,
  },
  addAttrBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  addAttrBtnText: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '600',
  },
  templatePresets: {
    marginBottom: 10,
  },
  templatePresetsLabel: {
    fontSize: 10,
    color: colors.textMuted,
    fontWeight: '600',
  },
  templateBtn: {
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginRight: 4,
  },
  templateBtnText: {
    fontSize: 10,
    color: colors.textSecondary,
  },
  attrInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  attrInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 6,
    color: colors.textPrimary,
    fontSize: 11,
  },
  removeAttrBtn: {
    padding: 6,
  },
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  btnCancel: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 6,
    backgroundColor: 'rgba(15, 23, 42, 0.05)',
  },
  btnCancelText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  btnSave: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 6,
    backgroundColor: colors.primary,
  },
  btnSaveText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
});
