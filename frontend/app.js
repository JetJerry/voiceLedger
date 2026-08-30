// VoiceLedger Frontend Interactive Application

const API_BASE = '/api';

// State
let isRecording = false;
let recognition = null;
let currentSimSale = null;

// DOM Elements
const micBtn = document.getElementById('mic-btn');
const voiceTextInput = document.getElementById('voice-text-input');
const sendVoiceBtn = document.getElementById('send-voice-btn');
const agentResponseBox = document.getElementById('agent-response-box');
const agentReplyText = document.getElementById('agent-reply-text');
const agentActionTag = document.getElementById('agent-action-tag');

// Metrics
const metricTodaySales = document.getElementById('metric-today-sales');
const metricCollected = document.getElementById('metric-collected');
const metricOutstanding = document.getElementById('metric-outstanding');
const countPaid = document.getElementById('count-paid');
const countPartial = document.getElementById('count-partial');
const countPending = document.getElementById('count-pending');

// Table
const salesTbody = document.getElementById('sales-tbody');
const refreshBtn = document.getElementById('refresh-btn');

// Modal Elements
const simulateModal = document.getElementById('simulate-modal');
const closeModalBtn = document.getElementById('close-modal-btn');
const simSaleId = document.getElementById('sim-sale-id');
const simItems = document.getElementById('sim-items');
const simExpectedAmt = document.getElementById('sim-expected-amt');
const simPaymentAmt = document.getElementById('sim-payment-amt');
const simFullBtn = document.getElementById('sim-full-btn');
const simPartialBtn = document.getElementById('sim-partial-btn');
const submitSimPaymentBtn = document.getElementById('submit-sim-payment-btn');

// Initialize Web Speech Recognition
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'hi-IN';

    recognition.onstart = () => {
      isRecording = true;
      micBtn.classList.add('recording');
      voiceTextInput.placeholder = 'Listening... Speak your sale or ask: Payment aaya kya?';
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      voiceTextInput.value = transcript;
      handleProcessVoice(transcript);
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      stopRecording();
    };

    recognition.onend = () => {
      stopRecording();
    };
  } else {
    console.info('Web Speech API not supported. You can type commands directly in the input box.');
  }
}

function startRecording() {
  if (recognition) {
    try {
      recognition.start();
    } catch (e) {
      console.error(e);
    }
  } else {
    alert('Microphone speech recognition requires Google Chrome or Edge. You can also type commands directly in the input box!');
  }
}

function stopRecording() {
  isRecording = false;
  micBtn.classList.remove('recording');
  voiceTextInput.placeholder = 'Speak a sale (e.g. 2 coffee 60 rupaye) or ask: Payment aaya kya?...';
}

// Process voice / text command
async function handleProcessVoice(textOverride = null) {
  const text = (textOverride || voiceTextInput.value).trim();
  if (!text) return;

  agentResponseBox.classList.remove('hidden');
  agentReplyText.innerText = 'Checking with VoiceLedger Agent...';
  agentActionTag.innerText = 'Processing';
  agentActionTag.style.display = 'inline-block';

  try {
    const res = await fetch(`${API_BASE}/voice/process-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    const data = await res.json();
    agentReplyText.innerText = data.agent_reply;
    agentActionTag.innerText = data.action_taken || 'Completed';

    // Neural TTS Audio Playback (Hindi / English Neural Voice)
    if (data.audio_base64) {
      const audio = new Audio(data.audio_base64);
      audio.play().catch(e => console.log('Audio autoplay prevented or error:', e));
    } else if ('speechSynthesis' in window && data.agent_reply) {
      const utterance = new SpeechSynthesisUtterance(data.agent_reply);
      utterance.lang = 'hi-IN';
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    }

    voiceTextInput.value = '';
    loadDashboard();
  } catch (err) {
    agentReplyText.innerText = `Error: ${err.message}`;
    agentActionTag.innerText = 'Failed';
  }
}

// Load Dashboard Summary & Sales List
async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/dashboard/summary`);
    if (!res.ok) return;

    const data = await res.json();

    // Update KPIs
    metricTodaySales.innerText = `₹${data.today_sales.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    metricCollected.innerText = `₹${data.total_collected.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    metricOutstanding.innerText = `₹${data.total_outstanding.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    
    countPaid.innerText = data.paid_count;
    countPartial.innerText = data.partial_count;
    countPending.innerText = data.pending_count;

    // Render Sales Table
    renderSalesTable(data.recent_sales);
  } catch (e) {
    console.error('Failed to load dashboard data:', e);
  }
}

// Render Sales Table
function renderSalesTable(sales) {
  if (!sales || sales.length === 0) {
    salesTbody.innerHTML = `<tr><td colspan="6" class="empty-state">No sales recorded yet. Speak a sale above to get started!</td></tr>`;
    return;
  }

  salesTbody.innerHTML = sales.map(s => {
    const itemsSummary = (s.items && s.items.length > 0)
      ? s.items.map(i => `${i.quantity}x ${i.product_name}`).join(', ')
      : (s.raw_voice_transcript || 'Order items');

    let badgeClass = 'badge-pending';
    let statusText = 'PENDING ⏳';
    if (s.status === 'PAID') {
      badgeClass = 'badge-paid';
      statusText = 'PAID ✅';
    } else if (s.status === 'PARTIAL') {
      badgeClass = 'badge-partial';
      statusText = 'PARTIAL ⚠️';
    }

    const rzpLinkBtn = s.razorpay_payment_link_url
      ? `<a href="${s.razorpay_payment_link_url}" target="_blank" class="btn btn-secondary btn-sm" title="Open Razorpay Checkout">💳 Pay Link</a>`
      : '';

    const simBtn = s.status !== 'PAID'
      ? `<button class="btn btn-primary btn-sm sim-pay-btn" data-sale-id="${s.id}" data-items="${itemsSummary}" data-expected="${s.total_amount}" data-outstanding="${s.outstanding_amount}">⚡ Pay Simulate</button>`
      : '';

    return `
      <tr>
        <td>
          <div class="customer-cell">${itemsSummary}</div>
          <div class="items-subtext">ID: ${s.id}</div>
        </td>
        <td><b>₹${s.total_amount.toFixed(2)}</b></td>
        <td class="text-success">₹${s.received_amount.toFixed(2)}</td>
        <td class="${s.outstanding_amount > 0 ? 'text-danger' : ''}">₹${s.outstanding_amount.toFixed(2)}</td>
        <td><span class="status-badge ${badgeClass}">${statusText}</span></td>
        <td>
          <div class="action-btn-group">
            ${rzpLinkBtn}
            ${simBtn}
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Attach modal click listeners
  document.querySelectorAll('.sim-pay-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      openSimulateModal({
        id: btn.dataset.saleId,
        items: btn.dataset.items,
        expected: parseFloat(btn.dataset.expected),
        outstanding: parseFloat(btn.dataset.outstanding)
      });
    });
  });
}

// Modal Handlers
function openSimulateModal(sale) {
  currentSimSale = sale;
  simSaleId.value = sale.id;
  simItems.value = sale.items;
  simExpectedAmt.value = `₹${sale.expected.toFixed(2)}`;
  simPaymentAmt.value = sale.outstanding.toFixed(2);
  simulateModal.classList.remove('hidden');
}

function closeSimulateModal() {
  simulateModal.classList.add('hidden');
  currentSimSale = null;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  initSpeechRecognition();
  loadDashboard();

  // Polling every 5 seconds for live webhook updates
  setInterval(loadDashboard, 5000);

  micBtn.addEventListener('click', () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  sendVoiceBtn.addEventListener('click', () => handleProcessVoice());

  voiceTextInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleProcessVoice();
  });

  refreshBtn.addEventListener('click', () => {
    loadDashboard();
  });

  // Prompt Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const promptText = chip.dataset.prompt;
      voiceTextInput.value = promptText;
      handleProcessVoice(promptText);
    });
  });

  // Modal Actions
  closeModalBtn.addEventListener('click', closeSimulateModal);

  simFullBtn.addEventListener('click', () => {
    if (currentSimSale) {
      simPaymentAmt.value = currentSimSale.outstanding.toFixed(2);
    }
  });

  simPartialBtn.addEventListener('click', () => {
    if (currentSimSale) {
      simPaymentAmt.value = (currentSimSale.outstanding / 2).toFixed(2);
    }
  });

  submitSimPaymentBtn.addEventListener('click', async () => {
    if (!currentSimSale) return;
    const amt = parseFloat(simPaymentAmt.value);
    if (isNaN(amt) || amt <= 0) {
      alert('Please enter a valid payment amount');
      return;
    }

    try {
      submitSimPaymentBtn.innerText = 'Processing Payment...';
      const res = await fetch(`${API_BASE}/payments/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sale_id: currentSimSale.id,
          amount: amt,
          status: 'captured'
        })
      });

      const data = await res.json();
      closeSimulateModal();
      loadDashboard();
    } catch (e) {
      alert(`Simulation failed: ${e.message}`);
    } finally {
      submitSimPaymentBtn.innerText = 'Process Test Payment';
    }
  });
});
