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
import { Lock, Store, ShieldCheck, UserCheck, Sparkles, ArrowRight, Server, Check, Edit2 } from 'lucide-react-native';
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
        setTestResult('🟢 Connected to Modal Cloud Backend!');
      } else {
        setServerStatus('error');
        setTestResult(`🔴 Backend returned status ${res.status}`);
      }
    } catch (e) {
      setServerStatus('error');
      setTestResult(`🔴 Connection error: ${e.message}`);
    }
  };

  useEffect(() => {
    checkConnection();
    // Load demo accounts for quick-click convenience
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
        // Persist session in localStorage for Web
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
      setErrorMessage(e.message || 'Login failed. Please check your credentials.');
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
      setErrorMessage(e.message || 'Registration failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.card, isMobile && styles.cardMobile]}>
        
        {/* Brand Banner */}
        <View style={styles.brandBanner}>
          <View style={styles.logoBadge}>
            <Store size={26} color="#ffffff" strokeWidth={2.5} />
          </View>
          <Text style={styles.appTitle}>VoiceLedger</Text>
          <Text style={styles.appTagline}>Voice-First Multi-Vendor Sales & Payment Platform</Text>
        </View>

        {/* Portal Role Switcher Tabs */}
        <View style={styles.roleTabsContainer}>
          <TouchableOpacity
            style={[styles.roleTab, selectedRole === 'merchant' && styles.roleTabActive]}
            onPress={() => handleRoleChange('merchant')}
            activeOpacity={0.8}
          >
            <Store size={16} color={selectedRole === 'merchant' ? '#ffffff' : colors.textSecondary} />
            <Text style={[styles.roleTabText, selectedRole === 'merchant' && styles.roleTabTextActive]}>
              🏪 Shopkeeper Portal
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.roleTab, selectedRole === 'admin' && styles.roleTabAdminActive]}
            onPress={() => handleRoleChange('admin')}
            activeOpacity={0.8}
          >
            <ShieldCheck size={16} color={selectedRole === 'admin' ? '#ffffff' : colors.textSecondary} />
            <Text style={[styles.roleTabText, selectedRole === 'admin' && styles.roleTabTextActive]}>
              ⚡ Platform Admin
            </Text>
          </TouchableOpacity>
        </View>

        {/* Error Alert Box */}
        {errorMessage ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>⚠️ {errorMessage}</Text>
          </View>
        ) : null}

        {/* ── 1. SHOPKEEPER PORTAL ── */}
        {selectedRole === 'merchant' && (
          <View>
            {/* Login / Register Toggle */}
            <View style={styles.subToggleRow}>
              <TouchableOpacity
                style={[styles.subToggleBtn, merchantMode === 'login' && styles.subToggleBtnActive]}
                onPress={() => { setMerchantMode('login'); setErrorMessage(''); }}
              >
                <Text style={[styles.subToggleText, merchantMode === 'login' && styles.subToggleTextActive]}>
                  Store Sign In
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.subToggleBtn, merchantMode === 'register' && styles.subToggleBtnActive]}
                onPress={() => { setMerchantMode('register'); setErrorMessage(''); }}
              >
                <Text style={[styles.subToggleText, merchantMode === 'register' && styles.subToggleTextActive]}>
                  ➕ Register New Store
                </Text>
              </TouchableOpacity>
            </View>

            {merchantMode === 'login' ? (
              /* Shopkeeper Sign In Form */
              <View style={styles.formWrap}>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Store Username / Identifier</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="e.g. kirana, bakery, stationery"
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
                    <Text style={styles.submitBtnText}>🚀 Enter Store Terminal</Text>
                  )}
                </TouchableOpacity>

                {/* 1-Click Demo Accounts */}
                {demoAccounts?.merchants?.length > 0 && (
                  <View style={styles.quickAccountsSection}>
                    <Text style={styles.quickAccountsTitle}>✨ 1-Click Quick Demo Stores:</Text>
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
              /* Shopkeeper Registration Form */
              <ScrollView style={styles.registerScroll}>
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Store / Business Name *</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="e.g. Fresh Mart Organics, City Medicals"
                    placeholderTextColor={colors.textMuted}
                    value={regName}
                    onChangeText={setRegName}
                  />
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Business Category</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
                    {BUSINESS_TYPES.map((bType) => (
                      <TouchableOpacity
                        key={bType}
                        style={[styles.catChip, regBusinessType === bType && styles.catChipActive]}
                        onPress={() => setRegBusinessType(bType)}
                      >
                        <Text style={[styles.catChipText, regBusinessType === bType && styles.catChipTextActive]}>
                          {bType}
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
                      placeholder="e.g. green_farm"
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
                      placeholder="Min 4 chars"
                      placeholderTextColor={colors.textMuted}
                      value={regPassword}
                      onChangeText={setRegPassword}
                      secureTextEntry
                    />
                  </View>
                </View>

                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Phone (Optional)</Text>
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
                    <Text style={styles.submitBtnText}>✨ Create Store & Open Terminal</Text>
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
              <Text style={styles.adminInfoTitle}>⚡ Platform Super Administrator</Text>
              <Text style={styles.adminInfoSub}>
                Oversight of all merchant stores, GMV monitoring, live payment flows, and store approvals.
              </Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Admin Username</Text>
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
              <Text style={styles.inputLabel}>Admin Security Key / Password</Text>
              <TextInput
                style={styles.textInput}
                placeholder="admin123"
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
                <Text style={styles.submitBtnText}>⚡ Authenticate Admin Access</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.quickAdminBtn}
              onPress={() => handleLogin('admin', 'admin123', 'admin')}
              activeOpacity={0.8}
            >
              <Text style={styles.quickAdminBtnText}>⚡ 1-Click Demo Admin Login</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── Server API Connection Badge & Config ── */}
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
                {serverStatus === 'connected' ? 'Cloud Backend Connected' : (serverStatus === 'error' ? 'Backend Disconnected' : 'Checking Backend...')}
              </Text>
            </View>
            <Text style={styles.serverConfigToggle}>{showServerConfig ? '▲ Close' : '⚙️ API Server'}</Text>
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
                  <Text style={styles.serverActionBtnText}>💾 Save & Test</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.serverActionBtnReset}
                  onPress={() => {
                    setCurrentApiUrl(DEFAULT_MODAL_API_URL);
                    setCustomApiBase(DEFAULT_MODAL_API_URL);
                    checkConnection(DEFAULT_MODAL_API_URL);
                  }}
                >
                  <Text style={styles.serverActionBtnResetText}>↺ Reset to Modal</Text>
                </TouchableOpacity>
              </View>
              {testResult ? <Text style={styles.testResultText}>{testResult}</Text> : null}
            </View>
          )}
        </View>

        {/* Portal Footer */}
        <View style={styles.cardFooter}>
          <Text style={styles.cardFooterText}>
            🔒 Secured with role-based store isolation and Razorpay payment tracking
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
    backgroundColor: colors.bgDark,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.borderColor,
    padding: 28,
    width: '100%',
    maxWidth: 520,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
  },
  cardMobile: {
    padding: 20,
  },
  brandBanner: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logoBadge: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
  },
  appTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: colors.textPrimary,
    letterSpacing: -0.5,
  },
  appTagline: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
    textAlign: 'center',
  },

  // Role Switcher Tabs
  roleTabsContainer: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 14,
    padding: 4,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: colors.borderColor,
  },
  roleTab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    gap: 8,
  },
  roleTabActive: {
    backgroundColor: colors.primary,
  },
  roleTabAdminActive: {
    backgroundColor: '#8b5cf6',
  },
  roleTabText: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  roleTabTextActive: {
    color: '#ffffff',
  },

  // Error Alert
  errorBox: {
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.3)',
    borderRadius: 10,
    padding: 10,
    marginBottom: 16,
  },
  errorText: {
    color: colors.accentRose,
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },

  // Sub Toggle (Sign in vs Register)
  subToggleRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginBottom: 18,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderColor,
    paddingBottom: 10,
  },
  subToggleBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  subToggleBtnActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
  },
  subToggleText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textMuted,
  },
  subToggleTextActive: {
    color: colors.primary,
    fontWeight: '800',
  },

  // Forms
  formWrap: {
    width: '100%',
  },
  registerScroll: {
    maxHeight: 380,
  },
  inputGroup: {
    marginBottom: 14,
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
    borderRadius: 10,
    paddingHorizontal: 14,
    height: 44,
    color: colors.textPrimary,
    fontSize: 14,
  },
  rowTwo: {
    flexDirection: 'row',
  },
  catChip: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
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
    borderRadius: 12,
    height: 46,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 6,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },
  submitBtnAdmin: {
    backgroundColor: '#8b5cf6',
    shadowColor: '#8b5cf6',
  },
  submitBtnText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '800',
  },

  // Quick Accounts
  quickAccountsSection: {
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.borderColor,
  },
  quickAccountsTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textMuted,
    marginBottom: 8,
  },
  quickAccountsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickAccountChip: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    flex: 1,
    minWidth: 140,
  },
  quickAccountName: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  quickAccountRole: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // Admin Banner
  adminInfoBanner: {
    backgroundColor: 'rgba(139, 92, 246, 0.12)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.25)',
    padding: 12,
    marginBottom: 16,
  },
  adminInfoTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#a78bfa',
    marginBottom: 2,
  },
  adminInfoSub: {
    fontSize: 11,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  quickAdminBtn: {
    backgroundColor: 'rgba(139, 92, 246, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.3)',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  quickAdminBtnText: {
    color: '#c4b5fd',
    fontSize: 13,
    fontWeight: '700',
  },

  // Card Footer
  cardFooter: {
    marginTop: 16,
    alignItems: 'center',
  },
  cardFooterText: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
  },

  // Server Connection Status & Config Box
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
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.06)',
  },
  serverStatusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
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
    fontWeight: '600',
  },
  serverConfigToggle: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '700',
    marginLeft: 8,
  },
  serverConfigBox: {
    marginTop: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    borderRadius: 10,
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
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: colors.borderColor,
    borderRadius: 8,
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
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  serverActionBtnResetText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  testResultText: {
    marginTop: 8,
    fontSize: 11,
    color: colors.textPrimary,
  },
});
