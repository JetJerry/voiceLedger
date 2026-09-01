import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  useWindowDimensions,
} from 'react-native';
import {
  Lock,
  Store,
  ShieldCheck,
  User,
  PlusCircle,
  Server,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  RefreshCw,
} from 'lucide-react-native';
import { colors } from '../theme/colors';
import { apiService } from '../services/apiService';
import { getApiBase, setCustomApiBase, DEFAULT_MODAL_API_URL } from '../config/api';

const BUSINESS_TYPES = [
  'Kirana & Grocery',
  'Fruits & Vegetables',
  'Pharmacy & Medical',
  'Bakery & Sweets',
  'Cafe & Fast Food',
  'Apparel & Fashion',
  'Hardware & Electrical',
  'General Retail',
];

export default function LoginScreen({ onLoginSuccess }) {
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  // Mode: 'merchant' | 'admin'
  const [selectedRole, setSelectedRole] = useState('merchant');
  
  // Merchant sub-mode: 'login' | 'register'
  const [merchantMode, setMerchantMode] = useState('login');

  // Form Fields
  const [username, setUsername] = useState('kirana');
  const [password, setPassword] = useState('shop123');

  // Register Fields
  const [regName, setRegName] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regBusinessType, setRegBusinessType] = useState('Kirana & Grocery');
  const [regPhone, setRegPhone] = useState('');

  // States
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [demoAccounts, setDemoAccounts] = useState(null);

  // Backend Connection Settings
  const [showServerConfig, setShowServerConfig] = useState(false);
  const [currentApiUrl, setCurrentApiUrl] = useState(getApiBase());
  const [serverStatus, setServerStatus] = useState('checking'); // 'connected' | 'error' | 'checking'
  const [testResult, setTestResult] = useState('');

  const checkConnection = async (targetUrl = null) => {
    setServerStatus('checking');
    setTestResult('');
    const base = targetUrl || getApiBase();
    try {
      const res = await fetch(`${base}/health`, { method: 'GET' });
      if (res.ok) {
        setServerStatus('connected');
        setTestResult('Connected to backend service');
      } else {
        setServerStatus('error');
        setTestResult(`Backend returned status ${res.status}`);
      }
    } catch (e) {
      setServerStatus('error');
      setTestResult(`Connection error: ${e.message}`);
    }
  };

  useEffect(() => {
    checkConnection();
    apiService.getDemoAccounts()
      .then((data) => {
        setDemoAccounts(data);
        setServerStatus('connected');
      })
      .catch((e) => {
        console.warn('Demo accounts error:', e.message);
        setServerStatus('error');
      });
  }, []);

  const handleRoleChange = (role) => {
    setSelectedRole(role);
    setErrorMessage('');
    if (role === 'admin') {
      setUsername('admin');
      setPassword('admin123');
    } else {
      setUsername('kirana');
      setPassword('shop123');
    }
  };

  const handleLogin = async (overrideUser = null, overridePass = null, overrideRole = null) => {
    const userToLogin = overrideUser || username;
    const passToLogin = overridePass || password;
    const roleToLogin = overrideRole || selectedRole;

    if (!userToLogin.trim()) {
      setErrorMessage('Please enter username');
      return;
    }
    if (!passToLogin.trim()) {
      setErrorMessage('Please enter password');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await apiService.login(userToLogin.trim(), passToLogin.trim(), roleToLogin);
      if (res.success && res.user) {
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.setItem('voiceledger_session', JSON.stringify({
            token: res.token,
            role: res.role,
            user: res.user,
          }));
        }
        onLoginSuccess(res.user, res.role, res.token);
      }
    } catch (e) {
      setErrorMessage(e.message || 'Authentication failed. Please check credentials or network connection.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!regName.trim()) {
      setErrorMessage('Store name is required');
      return;
    }
    if (!regUsername.trim()) {
      setErrorMessage('Username is required');
      return;
    }
    if (!regPassword.trim() || regPassword.length < 4) {
      setErrorMessage('Password must be at least 4 characters');
      return;
    }

    setIsLoading(true);
    setErrorMessage('');
    try {
      const res = await apiService.registerShopkeeper({
        name: regName.trim(),
        username: regUsername.trim().toLowerCase(),
        password: regPassword.trim(),
        business_type: regBusinessType,
        phone: regPhone.trim() || undefined,
      });

      if (res.success && res.user) {
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.setItem('voiceledger_session', JSON.stringify({
            token: res.token,
            role: res.role,
            user: res.user,
          }));
        }
        onLoginSuccess(res.user, res.role, res.token);
      }
    } catch (e) {
      setErrorMessage(e.message || 'Store registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.card, isMobile && styles.cardMobile]}>
        {/* Brand Header */}
        <View style={styles.brandBanner}>
          <View style={styles.brandLogo}>
            <Store size={22} color="#ffffff" strokeWidth={2.2} />
          </View>
          <Text style={styles.brandTitle}>VoiceLedger</Text>
          <Text style={styles.brandSubtitle}>
            Voice-First Financial Ledger & Payment Reconciliation Platform
          </Text>
        </View>

        {/* Portal Role Switcher Tabs */}
        <View style={styles.roleTabsContainer}>
          <TouchableOpacity
            style={[styles.roleTab, selectedRole === 'merchant' && styles.roleTabActive]}
            onPress={() => handleRoleChange('merchant')}
            activeOpacity={0.8}
          >
            <Store size={15} color={selectedRole === 'merchant' ? '#ffffff' : colors.textMuted} style={{ marginRight: 6 }} />
            <Text style={[styles.roleTabText, selectedRole === 'merchant' && styles.roleTabTextActive]}>
              Shopkeeper Portal
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.roleTab, selectedRole === 'admin' && styles.roleTabAdminActive]}
            onPress={() => handleRoleChange('admin')}
            activeOpacity={0.8}
          >
            <ShieldCheck size={15} color={selectedRole === 'admin' ? '#ffffff' : colors.textMuted} style={{ marginRight: 6 }} />
            <Text style={[styles.roleTabText, selectedRole === 'admin' && styles.roleTabTextActive]}>
              Platform Admin
            </Text>
          </TouchableOpacity>
        </View>

        {/* Error Alert Box */}
        {errorMessage ? (
          <View style={styles.errorBox}>
            <AlertCircle size={15} color={colors.accentRose} style={{ marginRight: 8, marginTop: 1 }} />
            <Text style={styles.errorText}>{errorMessage}</Text>
          </View>
        ) : null}

        {/* ── 1. SHOPKEEPER PORTAL ── */}
        {selectedRole === 'merchant' && (
          <View>
            <View style={styles.subToggleRow}>
              <TouchableOpacity
                style={[styles.subToggleBtn, merchantMode === 'login' && styles.subToggleBtnActive]}
                onPress={() => { setMerchantMode('login'); setErrorMessage(''); }}
                activeOpacity={0.8}
              >
                <User size={13} color={merchantMode === 'login' ? colors.primary : colors.textMuted} style={{ marginRight: 5 }} />
                <Text style={[styles.subToggleText, merchantMode === 'login' && styles.subToggleTextActive]}>
                  Store Sign In
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.subToggleBtn, merchantMode === 'register' && styles.subToggleBtnActive]}
                onPress={() => { setMerchantMode('register'); setErrorMessage(''); }}
                activeOpacity={0.8}
              >
                <PlusCircle size={13} color={merchantMode === 'register' ? colors.primary : colors.textMuted} style={{ marginRight: 5 }} />
                <Text style={[styles.subToggleText, merchantMode === 'register' && styles.subToggleTextActive]}>
                  Register New Store
                </Text>
              </TouchableOpacity>
            </View>

            {merchantMode === 'login' ? (
              <View style={styles.formWrap}>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Store Username</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="Enter store username (e.g. kirana)"
                    placeholderTextColor={colors.textMuted}
                    value={username}
                    onChangeText={setUsername}
                    autoCapitalize="none"
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Password</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="Enter password"
                    placeholderTextColor={colors.textMuted}
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry
                  />
                </View>

                <TouchableOpacity
                  style={styles.submitBtn}
                  onPress={() => handleLogin()}
                  disabled={isLoading}
                  activeOpacity={0.8}
                >
                  {isLoading ? (
                    <ActivityIndicator color="#ffffff" size="small" />
                  ) : (
                    <Text style={styles.submitBtnText}>Sign In to Terminal</Text>
                  )}
                </TouchableOpacity>

                {/* Quick Demo Accounts */}
                {demoAccounts?.merchants?.length > 0 && (
                  <View style={styles.quickAccountsSection}>
                    <Text style={styles.quickAccountsTitle}>Quick Access Demo Stores:</Text>
                    <View style={styles.quickAccountsGrid}>
                      {demoAccounts.merchants.map((m, idx) => (
                        <TouchableOpacity
                          key={idx}
                          style={styles.quickAccountChip}
                          onPress={() => handleLogin(m.username, m.password, 'merchant')}
                          activeOpacity={0.7}
                        >
                          <Text style={styles.quickAccountName}>{m.name}</Text>
                          <Text style={styles.quickAccountRole}>{m.business_type}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                )}
              </View>
            ) : (
              <ScrollView style={{ maxHeight: 380 }} showsVerticalScrollIndicator={false}>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Store Business Name *</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="e.g. Sharma General Store"
                    placeholderTextColor={colors.textMuted}
                    value={regName}
                    onChangeText={setRegName}
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Store Category</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginVertical: 4 }}>
                    {BUSINESS_TYPES.map((bt) => (
                      <TouchableOpacity
                        key={bt}
                        style={[styles.catChip, regBusinessType === bt && styles.catChipActive]}
                        onPress={() => setRegBusinessType(bt)}
                      >
                        <Text style={[styles.catChipText, regBusinessType === bt && styles.catChipTextActive]}>
                          {bt}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </View>

                <View style={styles.rowTwo}>
                  <View style={[styles.inputGroup, { flex: 1, marginRight: 6 }]}>
                    <Text style={styles.inputLabel}>Username *</Text>
                    <TextInput
                      style={styles.textInput}
                      placeholder="e.g. sharma_store"
                      placeholderTextColor={colors.textMuted}
                      value={regUsername}
                      onChangeText={setRegUsername}
                      autoCapitalize="none"
                    />
                  </View>

                  <View style={[styles.inputGroup, { flex: 1, marginLeft: 6 }]}>
                    <Text style={styles.inputLabel}>Password *</Text>
                    <TextInput
                      style={styles.textInput}
                      placeholder="Min 4 characters"
                      placeholderTextColor={colors.textMuted}
                      value={regPassword}
                      onChangeText={setRegPassword}
                      secureTextEntry
                    />
                  </View>
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Contact Phone (Optional)</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="+91 98765 43210"
                    placeholderTextColor={colors.textMuted}
                    value={regPhone}
                    onChangeText={setRegPhone}
                    keyboardType="phone-pad"
                  />
                </View>

                <TouchableOpacity
                  style={[styles.submitBtn, { backgroundColor: colors.accentEmerald }]}
                  onPress={handleRegister}
                  disabled={isLoading}
                  activeOpacity={0.8}
                >
                  {isLoading ? (
                    <ActivityIndicator color="#ffffff" size="small" />
                  ) : (
                    <Text style={styles.submitBtnText}>Create Account & Open Terminal</Text>
                  )}
                </TouchableOpacity>
              </ScrollView>
            )}
          </View>
        )}

        {/* ── 2. PLATFORM ADMIN PORTAL ── */}
        {selectedRole === 'admin' && (
          <View style={styles.formWrap}>
            <View style={styles.adminInfoBanner}>
              <ShieldCheck size={16} color={colors.accentViolet} style={{ marginRight: 8, marginTop: 1 }} />
              <View style={{ flex: 1 }}>
                <Text style={styles.adminInfoTitle}>Platform Administration Hub</Text>
                <Text style={styles.adminInfoSub}>
                  Consolidated oversight of merchant stores, transaction volumes, and live settlements.
                </Text>
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Admin Identifier</Text>
              <TextInput
                style={styles.textInput}
                placeholder="admin"
                placeholderTextColor={colors.textMuted}
                value={username}
                onChangeText={setUsername}
                autoCapitalize="none"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Security Key</Text>
              <TextInput
                style={styles.textInput}
                placeholder="Enter admin password"
                placeholderTextColor={colors.textMuted}
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />
            </View>

            <TouchableOpacity
              style={[styles.submitBtn, styles.submitBtnAdmin]}
              onPress={() => handleLogin(null, null, 'admin')}
              disabled={isLoading}
              activeOpacity={0.8}
            >
              {isLoading ? (
                <ActivityIndicator color="#ffffff" size="small" />
              ) : (
                <Text style={styles.submitBtnText}>Authenticate Admin</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.quickAdminBtn}
              onPress={() => handleLogin('admin', 'admin123', 'admin')}
              activeOpacity={0.8}
            >
              <Text style={styles.quickAdminBtnText}>1-Click Demo Admin Login</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Server Status & Configuration */}
        <View style={styles.serverConnectionWrap}>
          <TouchableOpacity
            style={styles.serverStatusBar}
            onPress={() => setShowServerConfig(!showServerConfig)}
            activeOpacity={0.7}
          >
            <View style={styles.serverStatusLeft}>
              <View style={[
                styles.statusDot,
                serverStatus === 'connected' ? styles.statusDotGreen : (serverStatus === 'error' ? styles.statusDotRed : styles.statusDotYellow)
              ]} />
              <Text style={styles.serverStatusText} numberOfLines={1}>
                {serverStatus === 'connected' ? 'Backend Service Online' : (serverStatus === 'error' ? 'Backend Offline' : 'Connecting...')}
              </Text>
            </View>
            <Text style={styles.serverConfigToggle}>{showServerConfig ? 'Close' : 'Configure Endpoint'}</Text>
          </TouchableOpacity>

          {showServerConfig && (
            <View style={styles.serverConfigBox}>
              <Text style={styles.serverConfigLabel}>Backend API Endpoint URL:</Text>
              <TextInput
                style={styles.serverConfigInput}
                value={currentApiUrl}
                onChangeText={setCurrentApiUrl}
                placeholder="https://...modal.run/api"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="none"
              />
              <View style={styles.serverConfigActions}>
                <TouchableOpacity
                  style={styles.serverActionBtnSave}
                  onPress={() => {
                    setCustomApiBase(currentApiUrl);
                    checkConnection(currentApiUrl);
                  }}
                >
                  <Text style={styles.serverActionBtnText}>Save & Test</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.serverActionBtnReset}
                  onPress={() => {
                    setCurrentApiUrl(DEFAULT_MODAL_API_URL);
                    setCustomApiBase(DEFAULT_MODAL_API_URL);
                    checkConnection(DEFAULT_MODAL_API_URL);
                  }}
                >
                  <Text style={styles.serverActionBtnResetText}>Reset Default</Text>
                </TouchableOpacity>
              </View>
              {testResult ? <Text style={styles.testResultText}>{testResult}</Text> : null}
            </View>
          )}
        </View>

        {/* Card Footer */}
        <View style={styles.cardFooter}>
          <Text style={styles.cardFooterText}>
            Secured with store isolation and Razorpay payment tracking
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minHeight: '100vh',
    width: '100%',
    backgroundColor: '#F8FAFC',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 32,
    width: '100%',
    maxWidth: 480,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
  },
  cardMobile: {
    padding: 20,
  },
  brandBanner: {
    alignItems: 'center',
    marginBottom: 24,
  },
  brandLogo: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  brandTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: -0.5,
  },
  brandSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 4,
    lineHeight: 16,
  },
  roleTabsContainer: {
    flexDirection: 'row',
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    borderRadius: 10,
    padding: 4,
    borderWidth: 1,
    borderColor: colors.borderColor,
    marginBottom: 20,
  },
  roleTab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 9,
    borderRadius: 8,
  },
  roleTabActive: {
    backgroundColor: colors.primary,
  },
  roleTabAdminActive: {
    backgroundColor: '#7c3aed',
  },
  roleTabText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  roleTabTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  subToggleRow: {
    flexDirection: 'row',
    marginBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
    paddingBottom: 4,
  },
  subToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    marginRight: 8,
    borderRadius: 6,
  },
  subToggleBtnActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
  },
  subToggleText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  subToggleTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.25)',
    padding: 10,
    marginBottom: 16,
  },
  errorText: {
    color: '#fb7185',
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
    lineHeight: 16,
  },
  formWrap: {
    width: '100%',
  },
  inputGroup: {
    marginBottom: 14,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 6,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 13,
  },
  rowTwo: {
    flexDirection: 'row',
  },
  catChip: {
    backgroundColor: 'rgba(15, 23, 42, 0.04)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    marginRight: 6,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  catChipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: colors.primary,
  },
  catChipText: {
    fontSize: 11,
    color: colors.textMuted,
  },
  catChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  submitBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    height: 42,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 6,
  },
  submitBtnAdmin: {
    backgroundColor: '#7c3aed',
  },
  submitBtnText: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
  },
  quickAccountsSection: {
    marginTop: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  quickAccountsTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
    marginBottom: 8,
  },
  quickAccountsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickAccountChip: {
    backgroundColor: 'rgba(15, 23, 42, 0.03)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    flex: 1,
    minWidth: 130,
  },
  quickAccountName: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  quickAccountRole: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 2,
  },
  adminInfoBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(124, 58, 237, 0.1)',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(124, 58, 237, 0.2)',
    padding: 12,
    marginBottom: 16,
  },
  adminInfoTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.accentViolet,
    marginBottom: 2,
  },
  adminInfoSub: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 15,
  },
  quickAdminBtn: {
    backgroundColor: 'rgba(124, 58, 237, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(124, 58, 237, 0.25)',
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
    marginTop: 10,
  },
  quickAdminBtnText: {
    color: colors.accentViolet,
    fontSize: 12,
    fontWeight: '600',
  },
  serverConnectionWrap: {
    marginTop: 18,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
    paddingTop: 12,
  },
  serverStatusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(15, 23, 42, 0.02)',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: 'rgba(15, 23, 42, 0.05)',
  },
  serverStatusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 8,
  },
  statusDotGreen: {
    backgroundColor: '#10b981',
  },
  statusDotRed: {
    backgroundColor: '#ef4444',
  },
  statusDotYellow: {
    backgroundColor: '#f59e0b',
  },
  serverStatusText: {
    fontSize: 11,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  serverConfigToggle: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '600',
    marginLeft: 8,
  },
  serverConfigBox: {
    marginTop: 8,
    backgroundColor: '#F8FAFC',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  serverConfigLabel: {
    fontSize: 11,
    color: colors.textMuted,
    fontWeight: '600',
    marginBottom: 6,
  },
  serverConfigInput: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    color: colors.textPrimary,
    fontSize: 12,
    marginBottom: 8,
  },
  serverConfigActions: {
    flexDirection: 'row',
    gap: 8,
  },
  serverActionBtnSave: {
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  serverActionBtnText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '700',
  },
  serverActionBtnReset: {
    backgroundColor: 'rgba(15, 23, 42, 0.05)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  serverActionBtnResetText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '500',
  },
  testResultText: {
    marginTop: 6,
    fontSize: 11,
    color: colors.textSecondary,
  },
  cardFooter: {
    marginTop: 14,
    alignItems: 'center',
  },
  cardFooterText: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
  },
});
