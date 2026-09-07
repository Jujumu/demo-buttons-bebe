/** Not imported by boot or listed in the production static manifest.
 * Preparation only: this adapter has no mutation method or activation flag.
 */
export function createCanonicalReviewAdapter(fetcher) {
  function ticketNumber(value) {
    if (typeof value !== 'string' || !/^gorgias:[1-9][0-9]{0,17}$/.test(value)) throw new Error('Invalid canonical ticket ID');
    return value.slice(8);
  }
  return Object.freeze({
    async load({inboxTicketId,sourceMessageId,draftRevision,recipient}) {
      ticketNumber(inboxTicketId);
      if(typeof sourceMessageId!=='string'||!sourceMessageId||sourceMessageId.length>200)throw new Error('Invalid source message ID');
      const params=new URLSearchParams({source_message_id:sourceMessageId});
      if(draftRevision!==undefined)params.set('draft_revision',draftRevision);
      if(recipient!==undefined)params.set('expected_recipient',recipient);
      const response=await fetcher('/console/api/inbox/review-context/'+encodeURIComponent(inboxTicketId)+'?'+params,
        {method:'GET',credentials:'same-origin',cache:'no-store'});
      const result=await response.json();
      if(!response.ok||!result.ok)throw new Error(result.error||'Review context unavailable');
      const context=result.context;
      if(context.inboxTicketId!==inboxTicketId||context.sourceMessageId!==sourceMessageId||context.sendEnabled!==false||context.sendAndCloseEnabled!==false)throw new Error('Review context mismatch');
      if(draftRevision!==undefined&&context.draftRevision!==draftRevision)throw new Error('Draft changed');
      if(recipient!==undefined&&context.recipient!==recipient.trim().toLowerCase())throw new Error('Recipient changed');
      return Object.freeze({...context});
    },
    snapshotForReview(context,text) {
      ticketNumber(context.inboxTicketId);
      if(context.sendEnabled!==false||context.sendAndCloseEnabled!==false||!context.reviewable)throw new Error('Context is not ready for review');
      if(typeof text!=='string'||!text.trim()||text.length>50000)throw new Error('Invalid review text');
      return Object.freeze({inboxTicketId:context.inboxTicketId,sourceMessageId:context.sourceMessageId,
        sourceRevision:context.sourceRevision,draftRevision:context.draftRevision,contextId:context.contextId,
        recipient:context.recipient,channel:context.channel,displayedDraft:context.draftText,reviewedText:text.trim(),
        sendEnabled:false,sendAndCloseEnabled:false});
    },
  });
}
