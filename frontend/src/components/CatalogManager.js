import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  PackageOpen,
  X,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  ArrowUpDown,
  Layers,
  Sparkles,
  Check,
  Maximize2,
  Minimize2,
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
  { label: '➕ Burger 100 rs', prompt: 'Burger 100 rupaye' },
  { label: '🔍 Coffee ka price?', prompt: 'Coffee ka price kya hai' },
  { label: '📋 Catalog list', prompt: 'Catalog batao kitne items hain' },
];

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 'ALL'];

export default function CatalogManager({ onCatalogUpdated }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  // Sorting & Pagination State
  const [sortField, setSortField] = useState('name'); // 'name' | 'price' | 'category'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc' | 'desc'
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [expandedRows, setExpandedRows] = useState({}); // { [productId]: boolean }
  const [allExpanded, setAllExpanded] = useState(false);

  // Modal State
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [formName, setFormName] = useState('');
  const [formPrice, setFormPrice] = useState('');
  const [formCategory, setFormCategory] = useState('General');
  const [formUnit, setFormUnit] = useState('piece');
  const [formDescription, setFormDescription] = useState('');
  const [formAttributes, setFormAttributes] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Business type & Multi-turn voice assistant state
  const [businessTypes, setBusinessTypes] = useState([]);
  const [selectedBusinessType, setSelectedBusinessType] = useState('Kirana & Retail');
  const [businessPresets, setBusinessPresets] = useState({});
  const [isSettingBusinessType, setIsSettingBusinessType] = useState(false);
  const [catalogVoiceText, setCatalogVoiceText] = useState('');
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);
  const [voiceResponse, setVoiceResponse] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [catalogConversationHistory, setCatalogConversationHistory] = useState([]);

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

    const currentHistory = [...catalogConversationHistory, { role: 'user', content: query }];

    try {
      const data = await apiService.processVoiceCommand(query, 'catalog', currentHistory);
      const reply = data.agent_reply || 'Done.';
      
      const updatedHistory = [...currentHistory, { role: 'assistant', content: reply }].slice(-10);
      setCatalogConversationHistory(updatedHistory);

      setVoiceResponse({
        reply,
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

  const toggleRowExpanded = (id) => {
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const toggleAllRows = () => {
    if (allExpanded) {
      setExpandedRows({});
      setAllExpanded(false);
    } else {
      const allObj = {};
      products.forEach((p) => {
        allObj[p.id] = true;
      });
      setExpandedRows(allObj);
      setAllExpanded(true);
    }
  };

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
    setCurrentPage(1);
  };

  const categories = useMemo(() => {
    return ['ALL', ...Array.from(new Set(products.map((p) => p.category || 'General')))];
  }, [products]);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      if (selectedCategory !== 'ALL' && (p.category || 'General') !== selectedCategory) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = (p.name || '').toLowerCase().includes(q);
        const matchCat = (p.category || '').toLowerCase().includes(q);
        const matchDesc = (p.description || '').toLowerCase().includes(q);
        const matchAttrs = Object.entries(p.attributes || {}).some(
          ([k, v]) => k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q)
        );
        return matchName || matchCat || matchDesc || matchAttrs;
      }
      return true;
    });
  }, [products, selectedCategory, searchQuery]);

  const sortedProducts = useMemo(() => {
    return [...filteredProducts].sort((a, b) => {
      let valA = a[sortField] || '';
      let valB = b[sortField] || '';

      if (sortField === 'price') {
        valA = Number(valA) || 0;
        valB = Number(valB) || 0;
      } else {
        valA = String(valA).toLowerCase();
        valB = String(valB).toLowerCase();
      }

      if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredProducts, sortField, sortOrder]);

  const totalPages = pageSize === 'ALL' ? 1 : Math.max(1, Math.ceil(sortedProducts.length / pageSize));
  
  const paginatedProducts = useMemo(() => {
    if (pageSize === 'ALL') return sortedProducts;
    const startIdx = (currentPage - 1) * pageSize;
    return sortedProducts.slice(startIdx, startIdx + pageSize);
  }, [sortedProducts, currentPage, pageSize]);

  const stats = useMemo(() => {
    const totalCount = products.length;
    const distinctCats = new Set(products.map((p) => p.category || 'General')).size;
    const avgPrice = totalCount > 0 ? products.reduce((acc, p) => acc + (p.price || 0), 0) / totalCount : 0;
    return {
      totalCount,
      distinctCats,
      avgPrice: avgPrice.toFixed(2),
    };
  }, [products]);

  return (
    <View style={styles.container}>
      {/* 1. Header Bar & Quick Metrics */}
      <View style={[styles.headerRow, isMobile && styles.headerRowMobile]}>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <View style={styles.headerBadge}>
              <Package size={18} color="#ffffff" strokeWidth={2.4} />
            </View>
            <Text style={styles.title}>Product Catalog & Inventory</Text>
          </View>
          <Text style={styles.subtitle}>
            High-density tabular ledger for {stats.totalCount} products across {stats.distinctCats} categories with dynamic multi-domain specifications.
          </Text>
        </View>

        <TouchableOpacity style={styles.addItemBtn} onPress={openAddModal} activeOpacity={0.85}>
          <Plus size={16} color="#ffffff" strokeWidth={2.4} style={{ marginRight: 6 }} />
          <Text style={styles.addItemBtnText}>Add Product</Text>
        </TouchableOpacity>
      </View>

      {/* Metrics Strip */}
      <View style={styles.metricsStrip}>
        <View style={styles.metricItem}>
          <Text style={styles.metricVal}>{stats.totalCount}</Text>
          <Text style={styles.metricLabel}>Total Items</Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={styles.metricVal}>{stats.distinctCats}</Text>
          <Text style={styles.metricLabel}>Categories</Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={[styles.metricVal, { color: colors.accentEmerald }]}>₹{stats.avgPrice}</Text>
          <Text style={styles.metricLabel}>Avg. Unit Price</Text>
        </View>
        <View style={styles.metricDivider} />
        <View style={styles.metricItem}>
          <Text style={[styles.metricVal, { color: colors.primary }]}>{filteredProducts.length}</Text>
          <Text style={styles.metricLabel}>Filtered Count</Text>
        </View>
      </View>

      {/* Store Type Selector */}
      <View style={styles.businessTypeCard}>
        <Text style={styles.businessTypeLabel}>🏪 Store Business Profile (Adaptive Schema)</Text>
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

      {/* Voice Assistant Panel with Multi-turn Memory */}
      <View style={styles.voicePanel}>
        <View style={styles.voicePanelHeader}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Sparkles size={16} color={colors.primary} />
            <Text style={styles.voicePanelTitle}>Voice-Assisted Catalog Assistant</Text>
          </View>
          <Text style={styles.voicePanelSub}>
            Multi-turn voice commands: "Add products" &gt; "Burger 100 rs", or "Menu dikhao", "Chai ka price?"
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
            placeholder="Bolein: 'Menu mein burger add karo 100 rupaye' ya 'Menu dikhao'..."
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
              <Text style={styles.voiceSendText}>Send</Text>
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

      {/* 2. Search, Category Filters, & Table Controls Bar */}
      <View style={styles.controlsCard}>
        {/* Search Input Row */}
        <View style={styles.searchRow}>
          <View style={styles.searchInputWrapper}>
            <Search size={16} color={colors.textMuted} style={{ marginRight: 8 }} />
            <TextInput
              style={styles.searchInput}
              placeholder="Search 100s of products by name, category, or specifications..."
              placeholderTextColor={colors.textMuted}
              value={searchQuery}
              onChangeText={(txt) => {
                setSearchQuery(txt);
                setCurrentPage(1);
              }}
            />
            {searchQuery ? (
              <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearBtn}>
                <X size={14} color={colors.textMuted} />
              </TouchableOpacity>
            ) : null}
          </View>

          {/* Expand/Collapse All Button */}
          <TouchableOpacity style={styles.expandAllBtn} onPress={toggleAllRows}>
            {allExpanded ? (
              <>
                <Minimize2 size={14} color={colors.textSecondary} style={{ marginRight: 4 }} />
                <Text style={styles.expandAllText}>Collapse All</Text>
              </>
            ) : (
              <>
                <Maximize2 size={14} color={colors.textSecondary} style={{ marginRight: 4 }} />
                <Text style={styles.expandAllText}>Expand All Specs</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Category Filter Chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.catScroll}>
          {categories.map((cat) => {
            const count = cat === 'ALL' ? products.length : products.filter((p) => (p.category || 'General') === cat).length;
            const isActive = selectedCategory === cat;
            return (
              <TouchableOpacity
                key={cat}
                style={[styles.catChip, isActive && styles.catChipActive]}
                onPress={() => {
                  setSelectedCategory(cat);
                  setCurrentPage(1);
                }}
              >
                <Text style={[styles.catChipText, isActive && styles.catChipTextActive]}>
                  {cat} ({count})
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* 3. Tabular Product View */}
      {isLoading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading inventory records...</Text>
        </View>
      ) : sortedProducts.length === 0 ? (
        <View style={styles.emptyBox}>
          <PackageOpen size={42} color={colors.textMuted} style={{ marginBottom: 10 }} />
          <Text style={styles.emptyTitle}>No products found</Text>
          <Text style={styles.emptySub}>
            {searchQuery ? 'No items match your search filter.' : 'Add your items manually or use voice: "Menu mein burger add karo 100 rupaye".'}
          </Text>
          <TouchableOpacity style={styles.emptyAddBtn} onPress={openAddModal}>
            <Text style={styles.emptyAddBtnText}>➕ Add First Product</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.tableCard}>
          {/* Table Header */}
          <View style={styles.tableHeaderRow}>
            <View style={[styles.thCol, { width: 44, justifyContent: 'center' }]}>
              <Text style={styles.thText}>#</Text>
            </View>

            <TouchableOpacity style={[styles.thCol, { flex: 2.2 }]} onPress={() => toggleSort('name')}>
              <Text style={styles.thText}>Item Name & Details</Text>
              <ArrowUpDown size={12} color={sortField === 'name' ? colors.primary : colors.textMuted} style={{ marginLeft: 4 }} />
            </TouchableOpacity>

            <TouchableOpacity style={[styles.thCol, { flex: 1.2 }]} onPress={() => toggleSort('category')}>
              <Text style={styles.thText}>Category</Text>
              <ArrowUpDown size={12} color={sortField === 'category' ? colors.primary : colors.textMuted} style={{ marginLeft: 4 }} />
            </TouchableOpacity>

            <View style={[styles.thCol, { flex: 1 }]}>
              <Text style={styles.thText}>Unit</Text>
            </View>

            <TouchableOpacity style={[styles.thCol, { flex: 1.2, justifyContent: 'flex-end' }]} onPress={() => toggleSort('price')}>
              <Text style={styles.thText}>Price</Text>
              <ArrowUpDown size={12} color={sortField === 'price' ? colors.primary : colors.textMuted} style={{ marginLeft: 4 }} />
            </TouchableOpacity>

            <View style={[styles.thCol, { flex: 1.8, paddingLeft: 12 }]}>
              <Text style={styles.thText}>Specifications</Text>
            </View>

            <View style={[styles.thCol, { width: 90, justifyContent: 'center' }]}>
              <Text style={styles.thText}>Actions</Text>
            </View>
          </View>

          {/* Table Body Rows */}
          {paginatedProducts.map((p, idx) => {
            const rowIndex = pageSize === 'ALL' ? idx + 1 : (currentPage - 1) * pageSize + idx + 1;
            const isExpanded = !!expandedRows[p.id];
            const attrs = p.attributes || {};
            const attrEntries = Object.entries(attrs);
            const isEven = idx % 2 === 0;

            return (
              <View key={p.id} style={[styles.tableRowWrapper, isEven ? styles.rowEven : styles.rowOdd]}>
                {/* Main Row Content */}
                <TouchableOpacity
                  style={styles.tableRow}
                  onPress={() => toggleRowExpanded(p.id)}
                  activeOpacity={0.7}
                >
                  {/* Row # */}
                  <View style={[styles.tdCol, { width: 44, justifyContent: 'center' }]}>
                    <Text style={styles.rowIdxText}>{rowIndex}</Text>
                  </View>

                  {/* Name & Description */}
                  <View style={[styles.tdCol, { flex: 2.2 }]}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Text style={styles.prodNameText}>
                        {p.name.charAt(0).toUpperCase() + p.name.slice(1)}
                      </Text>
                      {attrEntries.length > 0 && (
                        <View style={styles.specCountBadge}>
                          <Text style={styles.specCountText}>{attrEntries.length} specs</Text>
                        </View>
                      )}
                    </View>
                    {p.description ? (
                      <Text style={styles.prodDescShort} numberOfLines={1}>
                        {p.description}
                      </Text>
                    ) : null}
                  </View>

                  {/* Category */}
                  <View style={[styles.tdCol, { flex: 1.2 }]}>
                    <View style={styles.catPill}>
                      <Text style={styles.catPillText}>{p.category || 'General'}</Text>
                    </View>
                  </View>

                  {/* Unit */}
                  <View style={[styles.tdCol, { flex: 1 }]}>
                    <Text style={styles.unitText}>{p.unit ? `per ${p.unit}` : 'per piece'}</Text>
                  </View>

                  {/* Price */}
                  <View style={[styles.tdCol, { flex: 1.2, justifyContent: 'flex-end' }]}>
                    <View style={styles.pricePill}>
                      <Text style={styles.priceText}>₹{p.price.toFixed(2)}</Text>
                    </View>
                  </View>

                  {/* Specifications Preview */}
                  <View style={[styles.tdCol, { flex: 1.8, paddingLeft: 12 }]}>
                    {attrEntries.length > 0 ? (
                      <View style={styles.attrPillWrap}>
                        {attrEntries.slice(0, 2).map(([k, v]) => (
                          <View key={k} style={styles.inlineAttrTag}>
                            <Text style={styles.inlineAttrText}>
                              {k}: {String(v)}
                            </Text>
                          </View>
                        ))}
                        {attrEntries.length > 2 ? (
                          <Text style={styles.moreAttrsText}>+{attrEntries.length - 2} more</Text>
                        ) : null}
                      </View>
                    ) : (
                      <Text style={styles.noAttrsText}>Standard</Text>
                    )}
                  </View>

                  {/* Action Buttons & Expand Toggle */}
                  <View style={[styles.tdCol, { width: 90, justifyContent: 'flex-end', gap: 6 }]}>
                    <TouchableOpacity
                      style={styles.actionIconBtn}
                      onPress={(e) => {
                        e.stopPropagation?.();
                        openEditModal(p);
                      }}
                      title="Edit Product"
                    >
                      <Edit3 size={14} color={colors.primary} />
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={[styles.actionIconBtn, { backgroundColor: 'rgba(239, 68, 68, 0.08)' }]}
                      onPress={(e) => {
                        e.stopPropagation?.();
                        handleDeleteProduct(p.id);
                      }}
                      title="Deactivate Product"
                    >
                      <Trash2 size={14} color={colors.accentRose} />
                    </TouchableOpacity>

                    <View style={styles.chevronWrap}>
                      {isExpanded ? (
                        <ChevronUp size={16} color={colors.primary} />
                      ) : (
                        <ChevronDown size={16} color={colors.textMuted} />
                      )}
                    </View>
                  </View>
                </TouchableOpacity>

                {/* Expandable Accordion Panel */}
                {isExpanded && (
                  <View style={styles.expandedPanel}>
                    <View style={styles.expandedContentRow}>
                      {/* Left: Full Description & Metadata */}
                      <View style={styles.expandedLeft}>
                        <Text style={styles.expandedSectionLabel}>Item Overview & Description</Text>
                        <Text style={styles.expandedDescText}>
                          {p.description || 'No detailed description provided for this product.'}
                        </Text>
                        <View style={styles.expandedMetaRow}>
                          <Text style={styles.expandedMetaItem}>
                            <Text style={styles.expandedMetaKey}>Product ID: </Text>#{p.id}
                          </Text>
                          <Text style={styles.expandedMetaItem}>
                            <Text style={styles.expandedMetaKey}>Status: </Text>Active
                          </Text>
                          <Text style={styles.expandedMetaItem}>
                            <Text style={styles.expandedMetaKey}>Unit Price: </Text>₹{p.price.toFixed(2)} / {p.unit || 'piece'}
                          </Text>
                        </View>
                      </View>

                      {/* Right: Full Specifications Tags */}
                      <View style={styles.expandedRight}>
                        <Text style={styles.expandedSectionLabel}>Dynamic Domain Specifications</Text>
                        {attrEntries.length > 0 ? (
                          <View style={styles.expandedAttrsGrid}>
                            {attrEntries.map(([k, v]) => (
                              <View key={k} style={styles.fullAttrCard}>
                                <Text style={styles.fullAttrKey}>{k}</Text>
                                <Text style={styles.fullAttrVal}>{String(v)}</Text>
                              </View>
                            ))}
                          </View>
                        ) : (
                          <Text style={styles.noSpecsText}>No custom specifications defined. Click Edit to add specs.</Text>
                        )}
                      </View>
                    </View>

                    {/* Expand Footer Quick Action */}
                    <View style={styles.expandedFooter}>
                      <TouchableOpacity
                        style={styles.expandedEditBtn}
                        onPress={() => openEditModal(p)}
                      >
                        <Edit3 size={13} color="#ffffff" style={{ marginRight: 5 }} />
                        <Text style={styles.expandedEditBtnText}>Edit Product Details</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={styles.expandedDelBtn}
                        onPress={() => handleDeleteProduct(p.id)}
                      >
                        <Trash2 size={13} color={colors.accentRose} style={{ marginRight: 5 }} />
                        <Text style={styles.expandedDelBtnText}>Deactivate Item</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              </View>
            );
          })}

          {/* Table Footer: Pagination & Rows-Per-Page Selector */}
          <View style={styles.tableFooter}>
            <View style={styles.footerLeft}>
              <Text style={styles.pageInfoText}>
                Showing{' '}
                <Text style={{ fontWeight: '700', color: colors.textPrimary }}>
                  {pageSize === 'ALL'
                    ? sortedProducts.length
                    : Math.min(sortedProducts.length, (currentPage - 1) * pageSize + 1)}
                  -
                  {pageSize === 'ALL'
                    ? sortedProducts.length
                    : Math.min(sortedProducts.length, currentPage * pageSize)}
                </Text>{' '}
                of {sortedProducts.length} items
              </Text>

              {/* Rows Per Page */}
              <View style={styles.pageSizeWrapper}>
                <Text style={styles.pageSizeLabel}>Rows:</Text>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <TouchableOpacity
                    key={String(size)}
                    style={[styles.pageSizeChip, pageSize === size && styles.pageSizeChipActive]}
                    onPress={() => {
                      setPageSize(size);
                      setCurrentPage(1);
                    }}
                  >
                    <Text style={[styles.pageSizeText, pageSize === size && styles.pageSizeTextActive]}>
                      {size}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Pagination Buttons */}
            {pageSize !== 'ALL' && totalPages > 1 && (
              <View style={styles.paginationControls}>
                <TouchableOpacity
                  style={[styles.pageBtn, currentPage === 1 && styles.pageBtnDisabled]}
                  onPress={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  <Text style={[styles.pageBtnText, currentPage === 1 && styles.pageBtnTextDisabled]}>Previous</Text>
                </TouchableOpacity>

                <View style={styles.pageIndicator}>
                  <Text style={styles.pageIndicatorText}>
                    Page {currentPage} of {totalPages}
                  </Text>
                </View>

                <TouchableOpacity
                  style={[styles.pageBtn, currentPage === totalPages && styles.pageBtnDisabled]}
                  onPress={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  <Text style={[styles.pageBtnText, currentPage === totalPages && styles.pageBtnTextDisabled]}>Next</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
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
                  placeholder="e.g. Burger, Chai, Paracetamol 650, Shimla Apple, Notebook"
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
                    placeholder="e.g. piece, kg, plate, cup"
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
                  placeholder="e.g. Snacks, Beverages, Bakery, Pharmacy, Grocery"
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
                  placeholder="Product specifications or ingredients..."
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
                    <Text style={styles.attrsSub}>Flexible key-value parameters for domain specifications</Text>
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
                      placeholder="Key (e.g. Dietary, Size)"
                      placeholderTextColor={colors.textMuted}
                      value={attr.key}
                      onChangeText={(val) => handleUpdateAttribute(idx, 'key', val)}
                    />
                    <TextInput
                      style={[styles.attrInput, { flex: 1.2, marginRight: 6 }]}
                      placeholder="Value (e.g. Vegetarian, Large)"
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
  headerBadge: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 3,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    maxWidth: 680,
    lineHeight: 18,
  },
  addItemBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  addItemBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
  metricsStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 3,
    elevation: 1,
  },
  metricItem: {
    flex: 1,
    alignItems: 'center',
  },
  metricVal: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.3,
  },
  metricLabel: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  metricDivider: {
    width: 1,
    height: 28,
    backgroundColor: colors.borderColor,
  },
  businessTypeCard: {
    backgroundColor: '#ffffff',
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
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  businessTypeChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    borderColor: colors.primary,
  },
  businessTypeChipText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  businessTypeChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  voicePanel: {
    backgroundColor: '#F8FAFC',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.25)',
    padding: 16,
    marginBottom: 16,
    shadowColor: '#6366F1',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 5,
    elevation: 2,
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
    marginTop: 3,
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
    backgroundColor: '#ffffff',
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
    marginBottom: 6,
  },
  voiceChip: {
    backgroundColor: '#ffffff',
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
    backgroundColor: '#ffffff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(99, 102, 241, 0.2)',
    padding: 12,
    marginTop: 8,
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
  controlsCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 14,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 3,
    elevation: 1,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  searchInputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingHorizontal: 12,
    height: 40,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 13,
  },
  clearBtn: {
    padding: 4,
  },
  expandAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 40,
  },
  expandAllText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  catScroll: {
    flexDirection: 'row',
  },
  catChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginRight: 8,
  },
  catChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  catChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  catChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  loadingBox: {
    paddingVertical: 48,
    alignItems: 'center',
  },
  loadingText: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 10,
  },
  emptyBox: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderColor,
    paddingVertical: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 6,
  },
  emptySub: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 440,
    marginBottom: 16,
    lineHeight: 18,
  },
  emptyAddBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 22,
    paddingVertical: 11,
    borderRadius: 10,
  },
  emptyAddBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 13,
  },
  tableCard: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.borderColor,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  tableHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
  },
  thCol: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  thText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  tableRowWrapper: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
  },
  rowEven: {
    backgroundColor: '#ffffff',
  },
  rowOdd: {
    backgroundColor: '#FAFCFF',
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  tdCol: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowIdxText: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
  },
  prodNameText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  specCountBadge: {
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  specCountText: {
    fontSize: 10,
    color: colors.primary,
    fontWeight: '600',
  },
  prodDescShort: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  catPill: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#DBEAFE',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  catPillText: {
    fontSize: 11,
    color: '#1D4ED8',
    fontWeight: '600',
  },
  unitText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  pricePill: {
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  priceText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#047857',
  },
  attrPillWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  inlineAttrTag: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  inlineAttrText: {
    fontSize: 10,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  moreAttrsText: {
    fontSize: 10,
    color: colors.primary,
    fontWeight: '600',
  },
  noAttrsText: {
    fontSize: 11,
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  actionIconBtn: {
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  chevronWrap: {
    width: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  expandedPanel: {
    backgroundColor: '#F8FAFC',
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
    padding: 16,
  },
  expandedContentRow: {
    flexDirection: 'row',
    gap: 20,
    marginBottom: 12,
  },
  expandedLeft: {
    flex: 1.2,
  },
  expandedRight: {
    flex: 1.5,
  },
  expandedSectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 6,
  },
  expandedDescText: {
    fontSize: 12,
    color: colors.textPrimary,
    lineHeight: 18,
    marginBottom: 10,
  },
  expandedMetaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  expandedMetaItem: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  expandedMetaKey: {
    fontWeight: '700',
    color: colors.textPrimary,
  },
  expandedAttrsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  fullAttrCard: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minWidth: 100,
  },
  fullAttrKey: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textMuted,
    textTransform: 'uppercase',
  },
  fullAttrVal: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: 1,
  },
  noSpecsText: {
    fontSize: 12,
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  expandedFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  expandedEditBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  expandedEditBtnText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
  },
  expandedDelBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FEE2E2',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  expandedDelBtnText: {
    color: colors.accentRose,
    fontSize: 11,
    fontWeight: '700',
  },
  tableFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: '#F8FAFC',
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  footerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  pageInfoText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  pageSizeWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  pageSizeLabel: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
  },
  pageSizeChip: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  pageSizeChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pageSizeText: {
    fontSize: 10,
    color: colors.textMuted,
    fontWeight: '600',
  },
  pageSizeTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  paginationControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pageBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  pageBtnDisabled: {
    opacity: 0.5,
  },
  pageBtnText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  pageBtnTextDisabled: {
    color: colors.textMuted,
  },
  pageIndicator: {
    paddingHorizontal: 6,
  },
  pageIndicatorText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 540,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.borderColor,
    maxHeight: '90vh',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 5,
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
  modalScroll: {
    padding: 18,
    maxHeight: 480,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FEE2E2',
    padding: 10,
    marginBottom: 14,
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
    marginBottom: 4,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
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
    backgroundColor: '#F8FAFC',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    marginRight: 6,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  presetChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  presetChipText: {
    fontSize: 11,
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
    fontSize: 13,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  attrsSub: {
    fontSize: 11,
    color: colors.textMuted,
  },
  addAttrBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
  },
  addAttrBtnText: {
    fontSize: 11,
    color: colors.primary,
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
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
  },
  templateBtnText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  attrInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  attrInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
    color: colors.textPrimary,
    fontSize: 12,
  },
  removeAttrBtn: {
    padding: 6,
  },
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  btnCancel: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#F1F5F9',
  },
  btnCancelText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  btnSave: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: colors.primary,
  },
  btnSaveText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
});
